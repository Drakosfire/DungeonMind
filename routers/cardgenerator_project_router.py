"""
CardGenerator Project Router

Focused router for CardGenerator project management.
Integrates with the global session system for project context switching.

Extracted from monolithic cardgenerator_router.py as part of architectural refactoring.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth_router import get_current_user
from session_management import get_session, session_manager
import firestore.firestore_utils as firestore_utils

# Import CardSessionData from the compatibility router to maintain API contract
from .cardgenerator_router import CardSessionData

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cardgenerator/projects", tags=["CardGenerator Projects"])

def create_safe_card_session_data(state_data: Dict[str, Any], project_id: str) -> CardSessionData:
    """
    Safely create CardSessionData with proper defaults for required fields
    """
    # Ensure required fields have defaults
    safe_state = {
        "sessionId": state_data.get("sessionId", project_id),  # Use project_id as fallback
        "currentStep": state_data.get("currentStep", "text-generation"),  # Default to first step
        **state_data  # Override with any existing state data
    }
    return CardSessionData(**safe_state)

# Pydantic models
class ProjectMetadata(BaseModel):
    version: str = "1.0.0"
    tags: List[str] = []
    isTemplate: bool = False
    lastOpened: Optional[int] = None
    cardCount: int = 0

class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = None
    templateId: Optional[str] = None

class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[ProjectMetadata] = None

class ProjectSummaryResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    updatedAt: int
    cardCount: int
    previewImage: Optional[str] = None

class ProjectListResponse(BaseModel):
    projects: List[ProjectSummaryResponse]
    total: int

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    createdAt: int
    updatedAt: int
    userId: str
    state: CardSessionData
    metadata: ProjectMetadata

@router.post('/create', response_model=ProjectResponse)
async def create_project(
    request: CreateProjectRequest, 
    current_user=Depends(get_current_user),
    session_data=Depends(get_session)
):
    """Create a new CardGenerator project"""
    try:
        session, session_id = session_data
        user_id = current_user.sub
        project_id = str(uuid.uuid4())
        current_time = int(datetime.now().timestamp() * 1000)
        
        # Create project metadata
        project_metadata = ProjectMetadata(
            version="1.0.0",
            tags=[],
            isTemplate=False,
            lastOpened=current_time,
            cardCount=0
        )
        
        # Prepare project document
        project_doc = {
            "id": project_id,
            "user_id": user_id,
            "name": request.name,
            "description": request.description,
            "created_at": current_time,
            "updated_at": current_time,
            "metadata": project_metadata.dict(),
            "is_template": False,
            "tags": []
        }
        
        # Save to Firestore
        firestore_utils.add_document('cardgen_projects', project_id, project_doc)
        
        # Switch to new project in global session
        if session:
            await session_manager.update_tool_state(session_id, "cardgenerator", {
                "activeProjectId": project_id,
                "activeProjectName": request.name
            })
            logger.debug(f"Switched session {session_id} to new project {project_id}")
        
        logger.info(f"Created new CardGenerator project: {project_id} for user: {user_id}")
        
        return ProjectResponse(
            id=project_id,
            name=request.name,
            description=request.description,
            createdAt=current_time,
            updatedAt=current_time,
            userId=user_id,
            state=create_safe_card_session_data({}, project_id), # Empty state for new project
            metadata=project_metadata
        )
        
    except Exception as e:
        logger.error("Error creating project: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.get('/list', response_model=ProjectListResponse)
async def list_projects(
    includeTemplates: bool = False, 
    current_user=Depends(get_current_user)
):
    """Get all CardGenerator projects for a user"""
    try:
        user_id = current_user.sub
        
        # Query user's projects
        projects = firestore_utils.query_collection('cardgen_projects', 'user_id', '==', user_id)
        
        project_summaries = []
        for project_dict in projects:
            project_id = list(project_dict.keys())[0]
            project_data = list(project_dict.values())[0]
            
            # Skip templates if not requested
            if not includeTemplates and project_data.get('is_template', False):
                continue
                
            summary = ProjectSummaryResponse(
                id=project_id,
                name=project_data.get('name', 'Untitled Project'),
                description=project_data.get('description'),
                updatedAt=project_data.get('updated_at', 0),
                cardCount=project_data.get('metadata', {}).get('cardCount', 0),
                previewImage=project_data.get('preview_image')
            )
            project_summaries.append(summary)
        
        # Sort by updated date (most recent first)
        project_summaries.sort(key=lambda x: x.updatedAt, reverse=True)
        
        logger.info(f"Listed {len(project_summaries)} CardGenerator projects for user: {user_id}")
        
        return ProjectListResponse(
            projects=project_summaries,
            total=len(project_summaries)
        )
        
    except Exception as e:
        logger.error("Error listing projects: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

@router.get('/{project_id}', response_model=ProjectResponse)
async def get_project(
    project_id: str, 
    current_user=Depends(get_current_user),
    session_data=Depends(get_session)
):
    """Get full project data by ID and set as active project in session"""
    try:
        session, session_id = session_data
        user_id = current_user.sub
        
        # Get project from Firestore
        project_data = firestore_utils.get_document('cardgen_projects', project_id)
        
        if not project_data:
            raise HTTPException(status_code=404, detail="Project not found")
            
        # Verify ownership
        if project_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this project")
        
        # Update last opened timestamp
        current_time = int(datetime.now().timestamp() * 1000)
        project_data['metadata']['lastOpened'] = current_time
        project_data['updated_at'] = current_time
        
        firestore_utils.update_document('cardgen_projects', project_id, {
            'metadata.lastOpened': current_time,
            'updated_at': current_time
        })
        
        # Switch to this project in global session
        if session:
            await session_manager.update_tool_state(session_id, "cardgenerator", {
                "activeProjectId": project_id,
                "activeProjectName": project_data.get('name', 'Unknown')
            })
            logger.debug(f"Switched session {session_id} to project {project_id}")
        
        # Convert to response model
        response = ProjectResponse(
            id=project_id,
            name=project_data.get('name', 'Untitled Project'),
            description=project_data.get('description'),
            createdAt=project_data.get('created_at', 0),
            updatedAt=project_data.get('updated_at', 0),
            userId=project_data.get('user_id', ''),
            state=create_safe_card_session_data(project_data.get('state', {}), project_id),
            metadata=ProjectMetadata(**project_data.get('metadata', {}))
        )
        
        logger.info(f"Retrieved CardGenerator project: {project_id} for user: {user_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting project: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")

@router.put('/{project_id}')
async def update_project(
    project_id: str, 
    request: UpdateProjectRequest, 
    current_user=Depends(get_current_user),
    session_data=Depends(get_session)
):
    """Update project metadata"""
    try:
        session, session_id = session_data
        user_id = current_user.sub
        
        # Verify project exists and user owns it
        project_data = firestore_utils.get_document('cardgen_projects', project_id)
        
        if not project_data:
            raise HTTPException(status_code=404, detail="Project not found")
            
        if project_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this project")
        
        # Prepare update data
        current_time = int(datetime.now().timestamp() * 1000)
        update_data = {
            'updated_at': current_time
        }
        
        if request.name is not None:
            update_data['name'] = request.name
            
        if request.description is not None:
            update_data['description'] = request.description
            
        if request.metadata is not None:
            update_data['metadata'] = request.metadata.dict()
        
        # Update in Firestore
        firestore_utils.update_document('cardgen_projects', project_id, update_data)
        
        # Update session if this is the active project
        if session:
            cardgen_state = getattr(session, 'tool_states', {}).get('cardgenerator', {})
            if cardgen_state.get('activeProjectId') == project_id and request.name:
                await session_manager.update_tool_state(session_id, "cardgenerator", {
                    "activeProjectName": request.name
                })
        
        logger.info(f"Updated CardGenerator project: {project_id} for user: {user_id}")
        
        return {
            "success": True,
            "message": "Project updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating project: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")

@router.delete('/{project_id}')
async def delete_project(
    project_id: str, 
    current_user=Depends(get_current_user),
    session_data=Depends(get_session)
):
    """Delete project and associated resources"""
    try:
        session, session_id = session_data
        user_id = current_user.sub
        
        # Verify project exists and user owns it
        project_data = firestore_utils.get_document('cardgen_projects', project_id)
        
        if not project_data:
            raise HTTPException(status_code=404, detail="Project not found")
            
        if project_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this project")
        
        # Delete the project
        firestore_utils.delete_document('cardgen_projects', project_id)
        
        # Clear from session if this was the active project
        if session:
            cardgen_state = getattr(session, 'tool_states', {}).get('cardgenerator', {})
            if cardgen_state.get('activeProjectId') == project_id:
                await session_manager.update_tool_state(session_id, "cardgenerator", {
                    "activeProjectId": None,
                    "activeProjectName": None
                })
                logger.debug(f"Cleared active project from session {session_id}")
        
        logger.info(f"Deleted CardGenerator project: {project_id} for user: {user_id}")
        
        return {
            "success": True,
            "message": "Project deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting project: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")

@router.post('/{project_id}/duplicate', response_model=ProjectResponse)
async def duplicate_project(
    project_id: str, 
    new_name: str, 
    current_user=Depends(get_current_user),
    session_data=Depends(get_session)
):
    """Create a copy of an existing project"""
    try:
        session, session_id = session_data
        user_id = current_user.sub
        
        # Get original project
        original_project = firestore_utils.get_document('cardgen_projects', project_id)
        
        if not original_project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        if original_project.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to duplicate this project")
        
        # Create new project ID and timestamps
        new_project_id = str(uuid.uuid4())
        current_time = int(datetime.now().timestamp() * 1000)
        
        # Create duplicate project data
        duplicate_project = {
            "id": new_project_id,
            "user_id": user_id,
            "name": new_name,
            "description": f"Copy of {original_project.get('name', 'Untitled Project')}",
            "created_at": current_time,
            "updated_at": current_time,
            "state": original_project.get('state', {}),  # Copy original project state
            "metadata": {
                **original_project.get('metadata', {}),
                "lastOpened": current_time,
                "cardCount": 0  # Reset card count for new project
            },
            "is_template": False,
            "tags": original_project.get('tags', [])
        }
        
        # Save duplicate to Firestore
        firestore_utils.add_document('cardgen_projects', new_project_id, duplicate_project)
        
        # Switch to duplicated project in session
        if session:
            await session_manager.update_tool_state(session_id, "cardgenerator", {
                "activeProjectId": new_project_id,
                "activeProjectName": new_name
            })
        
        logger.info(f"Duplicated CardGenerator project: {project_id} to {new_project_id} for user: {user_id}")
        
        return ProjectResponse(
            id=new_project_id,
            name=new_name,
            description=duplicate_project['description'],
            createdAt=current_time,
            updatedAt=current_time,
            userId=user_id,
            state=create_safe_card_session_data(duplicate_project.get('state', {}), new_project_id),
            metadata=ProjectMetadata(**duplicate_project['metadata'])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error duplicating project: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to duplicate project: {str(e)}")