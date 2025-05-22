from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.growth import router, GrowthCreate, GrowthUpdate, GrowthResponse
from app.main.model.user import User
from app.main.service.growth_service import (
    create_growth,
    get_growths_for_baby,
    get_growth,
    update_growth,
    delete_growth
)
from app.main.service.baby_service import get_baby_if_authorized
from app.main.service.oauth_service import get_current_user


@router.post("/", response_model=GrowthResponse, status_code=status.HTTP_201_CREATED)
async def create_growth_record(
        growth: GrowthCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new growth measurement record (requires authentication and parent/co-parent relationship)"""
    # First create the growth record
    result = create_growth(db, growth.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to create growth record')
        )

    # Get the baby data for percentile calculation
    baby = get_baby_if_authorized(db, growth.baby_id, current_user.id)
    if isinstance(baby, dict):  # Error response
        return result  # Return the growth record without percentiles

    return result


@router.get("/baby/{baby_id}", response_model=List[GrowthResponse])
async def get_growths_by_baby(
        baby_id: int,
        skip: int = Query(0, description="Skip N records"),
        limit: int = Query(100, description="Limit to N records"),
        start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
        end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get growth measurement records for a baby (requires authentication and parent/co-parent relationship)"""
    result = get_growths_for_baby(db, baby_id, current_user.id, skip, limit, start_date, end_date)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve growth records')
        )

    return result


@router.get("/{growth_id}", response_model=GrowthResponse)
async def get_growth_record(
        growth_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get a specific growth measurement record (requires authentication and parent/co-parent relationship)"""
    result = get_growth(db, growth_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve growth record')
        )

    return result


@router.put("/{growth_id}", response_model=GrowthResponse)
async def update_growth_record(
        growth_id: int,
        growth_data: GrowthUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update a growth measurement record (requires authentication and parent/co-parent relationship)"""
    # First, get the existing growth record to get the baby_id
    existing_growth = get_growth(db, growth_id, current_user.id)
    if isinstance(existing_growth, dict) and existing_growth.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if existing_growth.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=existing_growth.get('message', 'Failed to retrieve growth record')
        )

    # Update the growth record
    result = update_growth(db, growth_id, growth_data.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to update growth record')
        )

    return result


@router.delete("/{growth_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_growth_record(
        growth_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete a growth measurement record (requires authentication and parent/co-parent relationship)"""
    result = delete_growth(db, growth_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to delete growth record')
        )

    return None
