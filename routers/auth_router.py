import os
from fastapi import APIRouter, Request, HTTPException, Depends
from authlib.integrations.starlette_client import OAuth, OAuthError
from starlette.responses import RedirectResponse, JSONResponse
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter()

# Load configuration based on environment
env = os.getenv('ENVIRONMENT', 'development')
logger.info(f"Current environment: {env}")

# Initialize OAuth without passing CONFIG directly
oauth = OAuth()

# Register the Google client
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    redirect_uri=os.environ.get('DUNGEONMIND_API_URL') + '/api/auth/callback',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    access_token_url='https://oauth2.googleapis.com/token',
    client_kwargs={'scope': 'openid profile email'},
)

# Check if the required environment variables are set
logger.info(f"Redirect URI: {os.environ.get('DUNGEONMIND_API_URL') + '/api/auth/callback'}")
if not google.client_id or not google.client_secret:
    raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env file or environment variables")

@router.get('/login')
async def login(request: Request):
    redirect_uri = os.environ.get('DUNGEONMIND_API_URL') + '/api/auth/callback'
    logger.info(f"Login request from: {request.headers.get('x-forwarded-proto', 'unknown')}://{request.headers.get('host', 'unknown')}")
    logger.info(f"Using redirect URI: {redirect_uri}")
    return await oauth.google.authorize_redirect(request, redirect_uri, nonce=request.session.get('nonce'))

@router.get('/callback')
async def auth_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user = await oauth.google.parse_id_token(token, nonce=request.session.get('nonce'))
        request.session['user'] = dict(user)
        return RedirectResponse(url='/')
    except Exception as e:
        # logger.error(f"Error during authorization: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))

@router.get('/profile')
async def profile(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Check if session has expired
    exp = request.session.get('exp')
    if exp and datetime.utcnow().timestamp() > exp:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session expired")
    
    return user

@router.get('/logout')
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url='/')

# Dependency to get current user
async def get_current_user(request: Request):
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Check if session has expired
    exp = request.session.get('exp')
    if exp and datetime.utcnow().timestamp() > exp:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Session expired")
    
    return user

# Use this dependency in routes that require authentication
@router.get('/protected-route')
async def protected_route(current_user: dict = Depends(get_current_user)):
    return {"message": "This is a protected route", "user": current_user}

@router.get('/current-user')
async def get_current_user(request: Request):
    # logger.info("'/current-user' endpoint accessed")
    
    # # Log the request details
    # logger.debug(f"Request headers: {request.headers}")
    # logger.debug(f"Request method: {request.method}")
    # logger.debug(f"Request URL: {request.url}")

    # # Log session information
    # logger.debug(f"Session data: {request.session}")
    
    user = request.session.get('user')
    if not user:
        # logger.warning("User not authenticated - no user in session")
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    
    # Check if session has expired
    exp = request.session.get('exp')
    current_time = datetime.utcnow().timestamp()
    # logger.debug(f"Session expiration: {exp}, Current time: {current_time}")
    
    if exp and current_time > exp:
        # logger.warning(f"Session expired. Exp: {exp}, Current time: {current_time}")
        request.session.clear()
        return JSONResponse(status_code=401, content={"detail": "Session expired"})
    
    # logger.info(f"User authenticated successfully: {user}")
    return user
