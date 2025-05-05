from datetime import datetime
from typing import Dict, List, Union, Any, Optional

from sqlalchemy.orm import Session

from app.main.model.doctor_visit import DoctorVisit
from app.main.service.baby_service import get_baby_if_authorized


def create_doctor_visit(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[DoctorVisit, Dict[str, str]]:
    """Create a new doctor visit record for a baby"""
    # Check if user is authorized to add doctor visit records for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Create new doctor visit record
    new_doctor_visit = DoctorVisit(
        created_at=datetime.utcnow(),
        visit_date=data['visit_date'],
        doctor_name=data['doctor_name'],
        visit_type=data['visit_type'],
        reason=data.get('reason'),
        diagnosis=data.get('diagnosis'),
        treatment=data.get('treatment'),
        notes=data.get('notes'),
        next_appointment=data.get('next_appointment'),
        baby_id=data['baby_id']
    )

    db.add(new_doctor_visit)
    db.commit()
    db.refresh(new_doctor_visit)
    return new_doctor_visit


def get_doctor_visits_for_baby(db: Session, baby_id: int, current_user_id: int,
                               skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> Union[List[DoctorVisit], Dict[str, str]]:
    """Get doctor visit records for a baby with optional date filtering"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query doctor visits
    query = db.query(DoctorVisit).filter(DoctorVisit.baby_id == baby_id)

    # Apply date filters if provided
    if start_date:
        query = query.filter(DoctorVisit.visit_date >= start_date)
    if end_date:
        query = query.filter(DoctorVisit.visit_date <= end_date)

    # Order by date descending (newest first)
    query = query.order_by(DoctorVisit.visit_date.desc())

    # Apply pagination
    doctor_visits = query.offset(skip).limit(limit).all()

    return doctor_visits


def get_doctor_visit(db: Session, doctor_visit_id: int, current_user_id: int) -> Union[DoctorVisit, Dict[str, str]]:
    """Get a specific doctor visit record by ID"""
    # Get the doctor visit record
    doctor_visit = db.query(DoctorVisit).filter(DoctorVisit.id == doctor_visit_id).first()

    if not doctor_visit:
        return {
            'status': 'fail',
            'message': 'Doctor visit record not found',
        }

    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, doctor_visit.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    return doctor_visit


def update_doctor_visit(db: Session, doctor_visit_id: int, data: Dict[str, Any], current_user_id: int) -> Union[
    DoctorVisit, Dict[str, str]]:
    """Update a doctor visit record"""
    # Get the doctor visit record
    doctor_visit = db.query(DoctorVisit).filter(DoctorVisit.id == doctor_visit_id).first()

    if not doctor_visit:
        return {
            'status': 'fail',
            'message': 'Doctor visit record not found',
        }

    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, doctor_visit.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Update doctor visit record
    doctor_visit.visit_date = data.get('visit_date', doctor_visit.visit_date)
    doctor_visit.doctor_name = data.get('doctor_name', doctor_visit.doctor_name)
    doctor_visit.visit_type = data.get('visit_type', doctor_visit.visit_type)
    doctor_visit.reason = data.get('reason', doctor_visit.reason)
    doctor_visit.diagnosis = data.get('diagnosis', doctor_visit.diagnosis)
    doctor_visit.treatment = data.get('treatment', doctor_visit.treatment)
    doctor_visit.notes = data.get('notes', doctor_visit.notes)
    doctor_visit.next_appointment = data.get('next_appointment', doctor_visit.next_appointment)

    db.commit()
    db.refresh(doctor_visit)
    return doctor_visit


def delete_doctor_visit(db: Session, doctor_visit_id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a doctor visit record"""
    # Get the doctor visit record
    doctor_visit = db.query(DoctorVisit).filter(DoctorVisit.id == doctor_visit_id).first()

    if not doctor_visit:
        return {
            'status': 'fail',
            'message': 'Doctor visit record not found',
        }

    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, doctor_visit.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Delete the doctor visit record
    db.delete(doctor_visit)
    db.commit()
    return {'status': 'DELETED'}