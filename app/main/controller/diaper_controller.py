from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.diaper import router, DiaperCreate, DiaperUpdate, DiaperResponse
from app.main.model.user import User
from app.main.service.diaper_service import (
    create_diaper,
    get_diapers_for_baby,
    get_diaper,
    update_diaper,
    delete_diaper
)
from app.main.service.oauth_service import get_current_user


@router.post("/", response_model=DiaperResponse, status_code=status.HTTP_201_CREATED)
async def create_diaper_record(
        diaper: DiaperCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new diaper record (requires authentication and parent/co-parent relationship)"""
    result = create_diaper(db, diaper.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to create diaper record')
        )

    return result


@router.get("/baby/{baby_id}", response_model=List[DiaperResponse])
async def get_diapers_by_baby(
        baby_id: int,
        skip: int = Query(0, description="Skip N records"),
        limit: int = Query(100, description="Limit to N records"),
        start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
        end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get diaper records for a baby (requires authentication and parent/co-parent relationship)"""
    result = get_diapers_for_baby(db, baby_id, current_user.id, skip, limit, start_date, end_date)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve diaper records')
        )

    return result


@router.get("/{diaper_id}", response_model=DiaperResponse)
async def get_diaper_record(
        diaper_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get a specific diaper record (requires authentication and parent/co-parent relationship)"""
    result = get_diaper(db, diaper_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve diaper record')
        )

    return result


@router.put("/{diaper_id}", response_model=DiaperResponse)
async def update_diaper_record(
        diaper_id: int,
        diaper_data: DiaperUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update a diaper record (requires authentication and parent/co-parent relationship)"""
    result = update_diaper(db, diaper_id, diaper_data.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to update diaper record')
        )

    return result


@router.delete("/{diaper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_diaper_record(
        diaper_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete a diaper record (requires authentication and parent/co-parent relationship)"""
    result = delete_diaper(db, diaper_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to delete diaper record')
        )

    return None