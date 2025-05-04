from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.sleep import router, SleepCreate, SleepUpdate, SleepResponse
from app.main.model.user import User
from app.main.service.sleep_service import (
    create_sleep,
    get_sleeps_for_baby,
    get_sleep,
    update_sleep,
    delete_sleep
)
from app.main.service.oauth_service import get_current_user


@router.post("/", response_model=SleepResponse, status_code=status.HTTP_201_CREATED)
async def create_sleep_record(
        sleep: SleepCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new sleep record (requires authentication and parent/co-parent relationship)"""
    result = create_sleep(db, sleep.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to create sleep record')
        )

    return result


@router.get("/baby/{baby_id}", response_model=List[SleepResponse])
async def get_sleeps_by_baby(
        baby_id: int,
        skip: int = Query(0, description="Skip N records"),
        limit: int = Query(100, description="Limit to N records"),
        start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
        end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get sleep records for a baby (requires authentication and parent/co-parent relationship)"""
    result = get_sleeps_for_baby(db, baby_id, current_user.id, skip, limit, start_date, end_date)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve sleep records')
        )

    return result


@router.get("/{sleep_id}", response_model=SleepResponse)
async def get_sleep_record(
        sleep_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get a specific sleep record (requires authentication and parent/co-parent relationship)"""
    result = get_sleep(db, sleep_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve sleep record')
        )

    return result


@router.put("/{sleep_id}", response_model=SleepResponse)
async def update_sleep_record(
        sleep_id: int,
        sleep_data: SleepUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update a sleep record (requires authentication and parent/co-parent relationship)"""
    result = update_sleep(db, sleep_id, sleep_data.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to update sleep record')
        )

    return result


@router.delete("/{sleep_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sleep_record(
        sleep_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete a sleep record (requires authentication and parent/co-parent relationship)"""
    result = delete_sleep(db, sleep_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to delete sleep record')
        )

    return None