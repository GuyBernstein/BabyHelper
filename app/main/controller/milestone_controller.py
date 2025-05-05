from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.milestone import router, MilestoneCreate, MilestoneUpdate, MilestoneResponse
from app.main.model.user import User
from app.main.service.milestone_service import (
    create_milestone,
    get_milestones_for_baby,
    get_milestone,
    update_milestone,
    delete_milestone
)
from app.main.service.oauth_service import get_current_user


@router.post("/", response_model=MilestoneResponse, status_code=status.HTTP_201_CREATED)
async def create_milestone_record(
        milestone: MilestoneCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new developmental milestone record (requires authentication and parent/co-parent relationship)"""
    result = create_milestone(db, milestone.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to create milestone record')
        )

    return result


@router.get("/baby/{baby_id}", response_model=List[MilestoneResponse])
async def get_milestones_by_baby(
        baby_id: int,
        skip: int = Query(0, description="Skip N records"),
        limit: int = Query(100, description="Limit to N records"),
        start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
        end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get developmental milestone records for a baby (requires authentication and parent/co-parent relationship)"""
    result = get_milestones_for_baby(db, baby_id, current_user.id, skip, limit, start_date, end_date)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve milestone records')
        )

    return result


@router.get("/{milestone_id}", response_model=MilestoneResponse)
async def get_milestone_record(
        milestone_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get a specific developmental milestone record (requires authentication and parent/co-parent relationship)"""
    result = get_milestone(db, milestone_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve milestone record')
        )

    return result


@router.put("/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone_record(
        milestone_id: int,
        milestone_data: MilestoneUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update a developmental milestone record (requires authentication and parent/co-parent relationship)"""
    result = update_milestone(db, milestone_id, milestone_data.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to update milestone record')
        )

    return result


@router.delete("/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_milestone_record(
        milestone_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete a developmental milestone record (requires authentication and parent/co-parent relationship)"""
    result = delete_milestone(db, milestone_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to delete milestone record')
        )

    return None