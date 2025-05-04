from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.health import router, HealthCreate, HealthUpdate, HealthResponse
from app.main.model.user import User
from app.main.service.health_service import (
    create_health_record,
    get_health_records_for_baby,
    get_health_record,
    update_health_record,
    delete_health_record
)
from app.main.service.oauth_service import get_current_user


@router.post("/", response_model=HealthResponse, status_code=status.HTTP_201_CREATED)
async def create_new_health_record(
        health: HealthCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new health record (requires authentication and parent/co-parent relationship)"""
    result = create_health_record(db, health.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to create health record')
        )

    return result


@router.get("/baby/{baby_id}", response_model=List[HealthResponse])
async def get_health_records_by_baby(
        baby_id: int,
        skip: int = Query(0, description="Skip N records"),
        limit: int = Query(100, description="Limit to N records"),
        start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
        end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get health records for a baby (requires authentication and parent/co-parent relationship)"""
    result = get_health_records_for_baby(db, baby_id, current_user.id, skip, limit, start_date, end_date)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve health records')
        )

    return result


@router.get("/{health_id}", response_model=HealthResponse)
async def get_specific_health_record(
        health_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get a specific health record (requires authentication and parent/co-parent relationship)"""
    result = get_health_record(db, health_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve health record')
        )

    return result


@router.put("/{health_id}", response_model=HealthResponse)
async def update_specific_health_record(
        health_id: int,
        health_data: HealthUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update a health record (requires authentication and parent/co-parent relationship)"""
    result = update_health_record(db, health_id, health_data.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to update health record')
        )

    return result


@router.delete("/{health_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_specific_health_record(
        health_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete a health record (requires authentication and parent/co-parent relationship)"""
    result = delete_health_record(db, health_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to delete health record')
        )

    return None