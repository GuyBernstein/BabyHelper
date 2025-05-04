from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.feeding import router, FeedingCreate, FeedingUpdate, FeedingResponse
from app.main.model.user import User
from app.main.service.feeding_service import (
    create_feeding,
    get_feedings_for_baby,
    get_feeding,
    update_feeding,
    delete_feeding
)
from app.main.service.oauth_service import get_current_user


@router.post("/", response_model=FeedingResponse, status_code=status.HTTP_201_CREATED)
async def create_feeding_record(
        feeding: FeedingCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new feeding record (requires authentication and parent/co-parent relationship)"""
    result = create_feeding(db, feeding.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to create feeding record')
        )

    return result


@router.get("/baby/{baby_id}", response_model=List[FeedingResponse])
async def get_feedings_by_baby(
        baby_id: int,
        skip: int = Query(0, description="Skip N records"),
        limit: int = Query(100, description="Limit to N records"),
        start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
        end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get feeding records for a baby (requires authentication and parent/co-parent relationship)"""
    result = get_feedings_for_baby(db, baby_id, current_user.id, skip, limit, start_date, end_date)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve feeding records')
        )

    return result


@router.get("/{feeding_id}", response_model=FeedingResponse)
async def get_feeding_record(
        feeding_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get a specific feeding record (requires authentication and parent/co-parent relationship)"""
    result = get_feeding(db, feeding_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve feeding record')
        )

    return result


@router.put("/{feeding_id}", response_model=FeedingResponse)
async def update_feeding_record(
        feeding_id: int,
        feeding_data: FeedingUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update a feeding record (requires authentication and parent/co-parent relationship)"""
    result = update_feeding(db, feeding_id, feeding_data.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to update feeding record')
        )

    return result


@router.delete("/{feeding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feeding_record(
        feeding_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete a feeding record (requires authentication and parent/co-parent relationship)"""
    result = delete_feeding(db, feeding_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to delete feeding record')
        )

    return None