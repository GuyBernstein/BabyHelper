from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.doctor_visit import router, DoctorVisitCreate, DoctorVisitUpdate, DoctorVisitResponse
from app.main.model.user import User
from app.main.service.doctor_visit_service import (
    create_doctor_visit,
    get_doctor_visits_for_baby,
    get_doctor_visit,
    update_doctor_visit,
    delete_doctor_visit
)
from app.main.service.oauth_service import get_current_user


@router.post("/", response_model=DoctorVisitResponse, status_code=status.HTTP_201_CREATED)
async def create_doctor_visit_record(
        doctor_visit: DoctorVisitCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new doctor visit record (requires authentication and parent/co-parent relationship)"""
    result = create_doctor_visit(db, doctor_visit.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to create doctor visit record')
        )

    return result


@router.get("/baby/{baby_id}", response_model=List[DoctorVisitResponse])
async def get_doctor_visits_by_baby(
        baby_id: int,
        skip: int = Query(0, description="Skip N records"),
        limit: int = Query(100, description="Limit to N records"),
        start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
        end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get doctor visit records for a baby (requires authentication and parent/co-parent relationship)"""
    result = get_doctor_visits_for_baby(db, baby_id, current_user.id, skip, limit, start_date, end_date)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve doctor visit records')
        )

    return result


@router.get("/{doctor_visit_id}", response_model=DoctorVisitResponse)
async def get_doctor_visit_record(
        doctor_visit_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get a specific doctor visit record (requires authentication and parent/co-parent relationship)"""
    result = get_doctor_visit(db, doctor_visit_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve doctor visit record')
        )

    return result


@router.put("/{doctor_visit_id}", response_model=DoctorVisitResponse)
async def update_doctor_visit_record(
        doctor_visit_id: int,
        doctor_visit_data: DoctorVisitUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update a doctor visit record (requires authentication and parent/co-parent relationship)"""
    result = update_doctor_visit(db, doctor_visit_id, doctor_visit_data.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to update doctor visit record')
        )

    return result


@router.delete("/{doctor_visit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_doctor_visit_record(
        doctor_visit_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete a doctor visit record (requires authentication and parent/co-parent relationship)"""
    result = delete_doctor_visit(db, doctor_visit_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to delete doctor visit record')
        )

    return None