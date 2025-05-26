from typing import Dict, Optional
from datetime import datetime, timedelta
import uuid
import logging
from fastapi import Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class GlobalSession:
    def __init__(self):
        self.ruleslawyer_loader = None
        self.storegenerator_state = None
        self.cardgenerator_state = None
        self.statblockgenerator_state = None
        self.last_accessed: datetime = datetime.now()
        self.user_id: Optional[str] = None

    def update_access_time(self):
        self.last_accessed = datetime.now()

class SessionStatus(BaseModel):
    active: bool
    last_accessed: datetime
    has_ruleslawyer: bool
    has_storegenerator: bool
    has_cardgenerator: bool
    has_statblockgenerator: bool
class GlobalSessionManager:
    def __init__(self, session_timeout_minutes: int = 20):
        self.sessions: Dict[str, GlobalSession] = {}
        self.session_timeout = timedelta(minutes=session_timeout_minutes)

    def create_session(self) -> str:
        """Create a new session and return its ID"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = GlobalSession()
        logger.info(f"Created new session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[GlobalSession]:
        """Retrieve a session by ID and update its access time"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.update_access_time()
            return session
        return None

    def cleanup_old_sessions(self):
        """Remove expired sessions"""
        current_time = datetime.now()
        expired_sessions = [
            sid for sid, session in self.sessions.items()
            if current_time - session.last_accessed > self.session_timeout
        ]
        for sid in expired_sessions:
            logger.info(f"Cleaning up expired session: {sid}")
            del self.sessions[sid]

    def get_session_status(self, session: GlobalSession) -> SessionStatus:
        """Get the current status of a session"""
        return SessionStatus(
            active=True,
            last_accessed=session.last_accessed,
            has_ruleslawyer=session.ruleslawyer_loader is not None,
            has_storegenerator=session.storegenerator_state is not None,
            has_cardgenerator=session.cardgenerator_state is not None
        )

# Create global session manager instance
session_manager = GlobalSessionManager()

async def get_session(session_id: str = None) -> tuple[GlobalSession, str]:
    """Dependency for getting or creating a session"""
    if not session_id:
        session_id = session_manager.create_session()
    
    session = session_manager.get_session(session_id)
    if not session:
        session_id = session_manager.create_session()
        session = session_manager.get_session(session_id)
    
    return session, session_id

# Export the session manager instance and dependency
__all__ = ['session_manager', 'get_session', 'GlobalSession', 'SessionStatus'] 