from datetime import datetime
from typing import Dict, List, Union, Any, Optional

from sqlalchemy.orm import Session

from app.main.model.medication import Medication
from app.main.service.baby_service import get_baby_if_authorized


def create_medication(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Medication, Dict[str, str]]:
    """Create a new medication record for a baby"""
    # Check if user is authorized to add medication records for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Create new medication record
    new_medication = Medication(
        created_at=datetime.utcnow(),
        name=data['name'],
        dosage=data['dosage'],
        dosage_unit=data['dosage_unit'],
        route=data['route'],
        time_given=data['time_given'],
        given_by=data.get('given_by'),
        reason=data.get('reason'),
        notes=data.get('notes'),
        baby_id=data['baby_id']
    )

    db.add(new_medication)
    db.commit()
    db.refresh(new_medication)
    return new_medication


def get_medications_for_baby(db: Session, baby_id: int, current_user_id: int,
                             skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None) -> Union[List[Medication], Dict[str, str]]:
    """Get medication records for a baby with optional date filtering"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query medications
    query = db.query(Medication).filter(Medication.baby_id == baby_id)

    # Apply date filters if provided
    if start_date:
        query = query.filter(Medication.time_given >= start_date)
    if end_date:
        query = query.filter(Medication.time_given <= end_date)

    # Order by time descending (newest first)
    query = query.order_by(Medication.time_given.desc())

    # Apply pagination
    medications = query.offset(skip).limit(limit).all()

    return medications


def get_medication(db: Session, medication_id: int, current_user_id: int) -> Union[Medication, Dict[str, str]]:
    """Get a specific medication record by ID"""
    # Get the medication record
    medication = db.query(Medication).filter(Medication.id == medication_id).first()

    if not medication:
        return {
            'status': 'fail',
            'message': 'Medication record not found',
        }

    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, medication.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    return medication


def update_medication(db: Session, medication_id: int, data: Dict[str, Any], current_user_id: int) -> Union[
    Medication, Dict[str, str]]:
    """Update a medication record"""
    # Get the medication record
    medication = db.query(Medication).filter(Medication.id == medication_id).first()

    if not medication:
        return {
            'status': 'fail',
            'message': 'Medication record not found',
        }

    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, medication.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Update medication record
    medication.name = data.get('name', medication.name)
    medication.dosage = data.get('dosage', medication.dosage)
    medication.dosage_unit = data.get('dosage_unit', medication.dosage_unit)
    medication.route = data.get('route', medication.route)
    medication.time_given = data.get('time_given', medication.time_given)
    medication.given_by = data.get('given_by', medication.given_by)
    medication.reason = data.get('reason', medication.reason)
    medication.notes = data.get('notes', medication.notes)

    db.commit()
    db.refresh(medication)
    return medication


def delete_medication(db: Session, medication_id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a medication record"""
    # Get the medication record
    medication = db.query(Medication).filter(Medication.id == medication_id).first()

    if not medication:
        return {
            'status': 'fail',
            'message': 'Medication record not found',
        }

    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, medication.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Delete the medication record
    db.delete(medication)
    db.commit()
    return {'status': 'DELETED'}