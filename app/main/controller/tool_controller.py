"""
Tool controller for API endpoints.
Handles HTTP requests for tool management and execution.
"""
from typing import List, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.tool import ToolResponse, ToolCreate, router, ToolUpdate, ToolExecutionRequest, \
    ToolExecutionResponse

from app.main.model.user import User
from app.main.service.tool_service import (
    create_tool, get_tool, get_active_tools, update_tool, execute_tool
)
from app.main.service.claude_api_service import ClaudeAPIService
from app.main.service.oauth_service import get_current_user, is_admin_user

# Initialize Claude API service
claude_service = ClaudeAPIService()


@router.post("/", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_new_tool(
        tool: ToolCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(is_admin_user)
):
    """
    Create a new tool (requires admin access).

    Tools are data extraction capabilities that can be used
    by the Claude API to process user queries.
    """
    try:
        result = create_tool(db, tool.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.get("/", response_model=List[ToolResponse])
async def list_tools(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get all active tools available to the user.

    Returns a list of tools that can be used for data extraction
    and analysis.
    """
    tools = get_active_tools(db)
    return tools


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool_details(
        tool_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific tool.

    Returns tool configuration, capabilities, and usage statistics.
    """
    tool = get_tool(db, tool_id)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    return tool


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool_config(
        tool_id: int,
        tool_data: ToolUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(is_admin_user)
):
    """
    Update a tool configuration (requires admin access).

    Allows updating tool capabilities, configuration, and status.
    """
    result = update_tool(db, tool_id, tool_data.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    return result


@router.post("/execute", response_model=ToolExecutionResponse)
async def execute_tool_endpoint(
        request: ToolExecutionRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Execute a specific tool with given parameters.

    This endpoint allows direct tool execution for testing
    or specific use cases.
    """
    try:
        result = execute_tool(
            db,
            request.tool_id,
            current_user.id,
            request.parameters,
            request.baby_id
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool execution failed: {str(e)}"
        )


@router.post("/query")
async def process_query(
        query: str,
        baby_id: Optional[int] = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Process a natural language query using appropriate tools.

    This endpoint uses the Claude API service to:
    1. Analyze the query
    2. Select appropriate tools
    3. Execute the tools
    4. Format results for response

    Example queries:
    - "Show me the last 10 activities for my baby"
    - "How has my baby been sleeping this week?"
    - "Who has been taking care of the baby today?"
    """
    try:
        result = await claude_service.process_query_with_tools(
            db,
            current_user.id,
            query,
            baby_id
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )

# Prepared for future SSE/WebSocket implementation
# @router.websocket("/stream")
# async def stream_query_results(
#     websocket: WebSocket,
#     db: Session = Depends(get_db)
# ):
#     """
#     WebSocket endpoint for streaming query results.
#     Prepared for future real-time implementation.
#     """
#     await websocket.accept()
#     # Implementation will be added when SSE/WebSocket is needed
#     await websocket.close()