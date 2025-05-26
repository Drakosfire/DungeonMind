from fastapi import APIRouter, Depends, HTTPException
from session_management import (
    session_manager, 
    get_session, 
    GlobalSession, 
    SessionStatus
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/init")
async def initialize_session():
    """Initialize a new session and return the session ID"""
    try:
        session_id = session_manager.create_session()
        logger.info(f"Initialized new session: {session_id}")
        return {
            "status": "success",
            "session_id": session_id,
            "message": "Session initialized successfully"
        }
    except Exception as e:
        logger.error(f"Failed to initialize session: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize session"
        )

@router.get("/status", response_model=SessionStatus)
async def get_session_status(session: GlobalSession = Depends(get_session)):
    """Get the current status of a session"""
    try:
        return session_manager.get_session_status(session)
    except Exception as e:
        logger.error(f"Failed to get session status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get session status"
        )

@router.delete("/cleanup")
async def cleanup_sessions():
    """Manually trigger cleanup of expired sessions"""
    try:
        initial_count = len(session_manager.sessions)
        session_manager.cleanup_old_sessions()
        final_count = len(session_manager.sessions)
        
        return {
            "status": "success",
            "message": f"Cleaned up {initial_count - final_count} expired sessions",
            "initial_sessions": initial_count,
            "remaining_sessions": final_count
        }
    except Exception as e:
        logger.error(f"Failed to cleanup sessions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to cleanup sessions"
        )

@router.get("/validate/{session_id}")
async def validate_session(session_id: str):
    """Validate if a session ID is active"""
    try:
        session = session_manager.get_session(session_id)
        return {
            "valid": session is not None,
            "message": "Session is valid" if session else "Session not found or expired"
        }
    except Exception as e:
        logger.error(f"Failed to validate session: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to validate session"
        )

@router.get("/info/{session_id}")
async def get_session_info(session_id: str):
    """Get detailed information about a specific session"""
    try:
        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail="Session not found"
            )
        
        return {
            "session_id": session_id,
            "last_accessed": session.last_accessed,
            "active_services": {
                "ruleslawyer": session.ruleslawyer_loader is not None,
                "storegenerator": session.storegenerator_state is not None,
                "cardgenerator": session.cardgenerator_state is not None
            },
            "user_id": session.user_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get session info"
        ) 