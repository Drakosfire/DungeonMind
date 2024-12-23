from fastapi import APIRouter, Request
import logging

logger = logging.getLogger(__name__)

debug_router = APIRouter()

@debug_router.get("/session")
async def debug_session(request: Request):
    # View current session data
    logger.debug(f"Request: {request}")
    session_data = request.session if request.session else "No session data available"
    logger.debug(f"Session data: {session_data}")
    return {"session_data": session_data}
