from datetime import datetime
from typing import Dict, List, Union, Any, Optional, Type

from sqlalchemy.orm import Session

from app.main.model import User
from app.main.model.health import Health, SymptomType
from app.main.service.baby_service import get_baby_if_authorized


def create_health_record(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Health, Dict[str, str]]:
    """Create a new health record for a baby"""
    # Check if user is authorized to add health records for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Process symptoms list into comma-separated string
    symptoms_str: Optional[str] = None
    if data.get('symptoms'):
        # Use the value of the enum if it's an enum, otherwise use the string
        string_symptoms = [symptom.value if hasattr(symptom, 'value') else str(symptom) for symptom in data['symptoms']]
        symptoms_str = ','.join(string_symptoms) if string_symptoms else None

    # Create new health record
    new_health = Health(
        created_at=datetime.utcnow(),
        time=data['time'],
        temperature=data.get('temperature'),
        symptoms=symptoms_str,
        medication=data.get('medication'),
        medication_dose=data.get('medication_dose'),
        notes=data.get('notes'),
        baby_id=data['baby_id'],
        recorded_by=current_user_id
    )

    db.add(new_health)
    db.commit()
    db.refresh(new_health)

    caregiver = db.query(User).filter(User.id == new_health.recorded_by).first()
    if caregiver:
        new_health.caregiver_name = caregiver.name

    # Convert symptoms string to list before returning
    _prepare_symptoms_for_response(new_health)
    return new_health


def get_health_records_for_baby(db: Session, baby_id: int, current_user_id: int,
                                skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None,
                                end_date: Optional[datetime] = None) -> Union[dict[str, str], list[Type[Health]]]:
    """Get health records for a baby with optional date filtering"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query health records
    query = db.query(Health).filter(Health.baby_id == baby_id)

    # Apply date filters if provided
    if start_date:
        query = query.filter(Health.time >= start_date)
    if end_date:
        query = query.filter(Health.time <= end_date)

    # Order by time descending (newest first)
    query = query.order_by(Health.time.desc())

    # Apply pagination
    health_records = query.offset(skip).limit(limit).all()

    # Add caregiver information to each health record
    for health_record in health_records:
        caregiver = db.query(User).filter(User.id == health_record.recorded_by).first()
        if caregiver:
            health_record.caregiver_name = caregiver.name

    # Process symptoms string back to list for each record
    for record in health_records:
        _prepare_symptoms_for_response(record)

    return health_records


def get_health_record(db: Session, health_id: int, current_user_id: int) -> Union[
    dict[str, str], dict[str, str], Type[Health]]:
    """Get a specific health record by ID"""
    # Get the health record
    health = db.query(Health).filter(Health.id == health_id).first()

    if not health:
        return {
            'status': 'fail',
            'message': 'Health record not found',
        }

    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, health.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    caregiver = db.query(User).filter(User.id == health.recorded_by).first()
    if caregiver:
        health.caregiver_name = caregiver.name

    # Convert symptoms string to list before returning
    _prepare_symptoms_for_response(health)
    return health


def update_health_record(db: Session, health_id: int, data: Dict[str, Any], current_user_id: int) -> Union[
    dict[str, str], dict[str, str], Type[Health]]:
    """Update a health record"""
    # Get the health record
    health = db.query(Health).filter(Health.id == health_id).first()

    if not health:
        return {
            'status': 'fail',
            'message': 'Health record not found',
        }

    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, health.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Process symptoms list into comma-separated string if provided
    if 'symptoms' in data:
        # Use the value of the enum if it's an enum, otherwise use the string
        string_symptoms = [symptom.value if hasattr(symptom, 'value') else str(symptom) for symptom in data['symptoms']]
        symptoms_str = ','.join(string_symptoms) if string_symptoms else None
        health.symptoms = symptoms_str

    # Update health record
    health.time = data.get('time', health.time)
    health.temperature = data.get('temperature', health.temperature)
    health.medication = data.get('medication', health.medication)
    health.medication_dose = data.get('medication_dose', health.medication_dose)
    health.notes = data.get('notes', health.notes)

    db.commit()
    db.refresh(health)

    caregiver = db.query(User).filter(User.id == health.recorded_by).first()
    if caregiver:
        health.caregiver_name = caregiver.name

    # Convert symptoms string to list before returning
    _prepare_symptoms_for_response(health)
    return health


def delete_health_record(db: Session, health_id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a health record"""
    # Get the health record
    health = db.query(Health).filter(Health.id == health_id).first()

    if not health:
        return {
            'status': 'fail',
            'message': 'Health record not found',
        }

    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, health.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Delete the health record
    db.delete(health)
    db.commit()
    return {'status': 'DELETED'}


def _prepare_symptoms_for_response(health: Health) -> None:
    """Helper function to convert symptoms string to list for response"""
    if health.symptoms:
        # Convert the comma-separated string to a list of SymptomType
        health.symptoms = [SymptomType(s.strip()) for s in health.symptoms.split(',')]
    else:
        health.symptoms = []