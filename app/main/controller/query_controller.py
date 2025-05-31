from datetime import datetime

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.config import CLAUDEConfig
from app.main.model import User, Baby
from app.main.model.query import ClaudeAPIConfig, router, QueryResponse, QueryRequest, ToolSelectionResponse
from app.main.service.claude_api_service import ClaudeAPIService
from app.main.service.oauth_service import get_current_user
from app.main.service.tool_service import get_active_tools

# Initialize Claude service with configuration
claude_config = ClaudeAPIConfig(
    model="claude-sonnet-4-20250514",
    max_tokens=20000,
    temperature=1,
    enable_thinking=True,
    max_tools_per_query=3
)

claude_service = ClaudeAPIService(
    api_key=CLAUDEConfig.API_KEY_CLAUDE,
    config=claude_config
)


@router.post("/query", response_model=QueryResponse)
async def process_query(
        request: QueryRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Process a natural language query using Claude AI-powered tool selection.
    Now uses structured request/response models for better API documentation.
    """

    # Validate baby ownership if baby_id is provided
    if request.baby_id:
        baby = db.query(Baby).filter(
            Baby.id == request.baby_id,
            Baby.parent_id == current_user.id
        ).first()

        if not baby:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Baby not found or access denied"
            )

    try:
        # Process query using Claude service
        result = await claude_service.process_query_with_tools(
            db=db,
            user_id=current_user.id,
            query=request.query,
            baby_id=request.baby_id,
            stream=request.stream,
            include_thinking=request.include_thinking
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Query processing failed"
            )

        # Return structured response
        return QueryResponse(
            success=True,
            data=result.data,
            metadata={
                "query_info": {
                    "original_query": request.query,
                    "baby_id": request.baby_id,
                    "processing_timestamp": datetime.utcnow().isoformat()
                },
                "tool_selection": result.tool_selection.to_dict(),
                "execution_summary": result.execution_summary,
                "processing_metadata": result.processing_metadata,
                "thinking_process": result.tool_selection.thinking_process if request.include_thinking else None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error in query processing: {str(e)}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during query processing"
        )


@router.post("/query/debug", response_model=ToolSelectionResponse)
async def debug_query_processing(
        request: QueryRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Debug endpoint using structured response models.
    """

    try:
        available_tools = get_active_tools(db)

        # Run tool selection only
        tool_selection_result = await claude_service.select_tools_for_query(
            db=db,
            query=request.query,
            available_tools=available_tools,
            baby_id=request.baby_id,
            include_thinking=request.include_thinking  # Pass include_thinking for debug too
        )

        return ToolSelectionResponse(
            query=request.query,
            baby_id=request.baby_id,
            available_tools=[
                {
                    "id": tool.id,
                    "name": tool.name,
                    "type": tool.tool_type.value,
                    "active": tool.is_active,
                    "description": tool.description
                } for tool in available_tools
            ],
            selected_tools=tool_selection_result.tool_info,
            reasoning=tool_selection_result.reasoning,
            confidence=tool_selection_result.confidence,
            query_classification=tool_selection_result.query_classification,
            thinking_process=tool_selection_result.thinking_process,
            fallback_used=tool_selection_result.fallback_used,
            processing_time_ms=tool_selection_result.selection_time_ms or 0.0
        )

    except Exception as e:
        # Return error in structured format
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Debug processing failed: {str(e)}"
        )