from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.pumping import router, PumpingCreate, PumpingUpdate, PumpingResponse
from app.main.model.user import User
from app.main.service.pumping_service import (
    create_pumping,
    get_pumpings_for_user,
    get_pumping,
    update_pumping,
    delete_pumping
)
from app.main.service.oauth_service import get_current_user


@router.post("/", response_model=PumpingResponse, status_code=status.HTTP_201_CREATED)
async def create_pumping_record(
        pumping: PumpingCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new pumping session record (requires authentication)"""
    result = create_pumping(db, pumping.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get('message', 'Failed to create pumping record')
        )

    return result


@router.get("/", response_model=List[PumpingResponse])
async def get_pumping_sessions(
        skip: int = Query(0, description="Skip N records"),
        limit: int = Query(100, description="Limit to N records"),
        start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
        end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get pumping session records for the current user"""
    result = get_pumpings_for_user(db, current_user.id, skip, limit, start_date, end_date)
    return result


@router.get("/{pumping_id}", response_model=PumpingResponse)
async def get_pumping_record(
        pumping_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get a specific pumping session record (requires authentication)"""
    result = get_pumping(db, pumping_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get('message', 'Failed to retrieve pumping record')
        )

    return result


@router.put("/{pumping_id}", response_model=PumpingResponse)
async def update_pumping_record(
        pumping_id: int,
        pumping_data: PumpingUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update a pumping session record (requires authentication)"""
    result = update_pumping(db, pumping_id, pumping_data.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get('message', 'Failed to update pumping record')
        )

    return result


@router.delete("/{pumping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pumping_record(
        pumping_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete a pumping session record (requires authentication)"""
    result = delete_pumping(db, pumping_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get('message', 'Failed to delete pumping record')
        )

    return None