from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from contextlib import asynccontextmanager
from fastapi import Depends


import os
import logging
from dotenv import load_dotenv


logger = logging.getLogger(__name__)

# Get the current environment
env = os.environ.get('ENVIRONMENT', 'development')
if env == 'production':
    load_dotenv('.env.production')
    logger.info(f"Production environment detected.")
else:
    load_dotenv('.env.development')
    logger.info(f"Development environment detected.")

# Import routers AFTER loading the environment variables
from routers import (
    auth_router,
    session_router,
    store_router,
    lawyer_router,
    cardgenerator_router
)

# Import session_manager
from session_management import get_session

# Import RulesLawyerService
from routers.ruleslawyer_router import RulesLawyerService

app = FastAPI()

# Initialize RulesLawyerService
rules_lawyer_service = RulesLawyerService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan function to preload embeddings on app startup."""
    try:
        logger.info("Starting application and loading default embeddings...")
        # Load default embeddings into memory
        rules_lawyer_service.load_embeddings_on_startup()
        logger.info("Default embeddings successfully cached.")
        yield  # Application runs here
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise e
    finally:
        logger.info("Cleaning up resources...")


# Set allowed hosts based on the environment
# This is a comma-separated list of hosts, so we need to split it
allowed_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
logger.info(f"Allowed hosts: {allowed_hosts}")
react_landing_url = os.environ.get('REACT_LANDING_URL')
logger.info(f"React landing URL: {react_landing_url}")



# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_hosts,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add SessionMiddleware
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.environ.get("SESSION_SECRET_KEY"),
    same_site="lax",  # This allows cookies to be sent in cross-site requests
    https_only=True, # Set to True in production
    domain=".dungeonmind.net" # Set to .dungeonmind.net in production
)
# Add the middleware with the appropriate allowed hosts (this used to be first)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Routers
app.include_router(
    session_router,
    prefix="/api/session",
    tags=["session"]
)

app.include_router(
    auth_router, 
    prefix='/api/auth',
    tags=["auth"],
    dependencies=[Depends(get_session)]
)

app.include_router(
    store_router, 
    prefix="/api/store",
    tags=["store"],
    dependencies=[Depends(get_session)]
)

app.include_router(
    lawyer_router, 
    prefix="/api/ruleslawyer",
    tags=["ruleslawyer"],
    dependencies=[Depends(get_session)]
)

app.include_router(
    cardgenerator_router, 
    prefix="/api/cardgenerator",
    tags=["cardgenerator"],
    dependencies=[Depends(get_session)]
)

# Health check route
@app.get("/health", response_class=JSONResponse)
async def health_check():
    return {"status": "ok"}

# Serve React app directly
@app.get("/", response_class=RedirectResponse)
async def serve_react_app():
    return RedirectResponse(url=react_landing_url)

#return the dungeonmind server api root url
@app.get("/config")
async def get_config():
    return {"DUNGEONMIND_API_URL": os.environ.get('DUNGEONMIND_API_URL')}


# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/saved_data", StaticFiles(directory="saved_data"), name="saved_data")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
