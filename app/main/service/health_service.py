from datetime import datetime
from typing import Dict, List, Union, Any, Optional

from sqlalchemy.orm import Session

from app.main.model.health import Health, SymptomType
from app.main.service.baby_service import get_baby_if_authorized


def create_health_record(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Health, Dict[str, str]]:
    """Create a new health record for a baby"""
    # Check if user is authorized to add health records for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Process symptoms list into comma-separated string
    symptoms_str = None
    if data.get('symptoms'):
        symptoms_str = ','.join([symptom for symptom in data['symptoms']])

    # Create new health record
    new_health = Health(
        created_at=datetime.utcnow(),
        time=data['time'],
        temperature=data.get('temperature'),
        symptoms=symptoms_str,
        medication=data.get('medication'),
        medication_dose=data.get('medication_dose'),
        notes=data.get('notes'),
        baby_id=data['baby_id']
    )

    db.add(new_health)
    db.commit()
    db.refresh(new_health)
    return new_health


def get_health_records_for_baby(db: Session, baby_id: int, current_user_id: int, 
                              skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None, 
                              end_date: Optional[datetime] = None) -> Union[List[Health], Dict[str, str]]:
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
    
    # Process symptoms string back to list for each record
    for record in health_records:
        if record.symptoms:
            record.symptoms_list = [SymptomType(s.strip()) for s in record.symptoms.split(',')]
        else:
            record.symptoms_list = []
    
    return health_records


def get_health_record(db: Session, health_id: int, current_user_id: int) -> Union[Health, Dict[str, str]]:
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
    
    # Process symptoms string back to list
    if health.symptoms:
        health.symptoms_list = [SymptomType(s.strip()) for s in health.symptoms.split(',')]
    else:
        health.symptoms_list = []
    
    return health


def update_health_record(db: Session, health_id: int, data: Dict[str, Any], current_user_id: int) -> Union[Health, Dict[str, str]]:
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
        symptoms_str = ','.join([symptom for symptom in data['symptoms']]) if data['symptoms'] else None
        health.symptoms = symptoms_str
    
    # Update health record
    health.time = data.get('time', health.time)
    health.temperature = data.get('temperature', health.temperature)
    health.medication = data.get('medication', health.medication)
    health.medication_dose = data.get('medication_dose', health.medication_dose)
    health.notes = data.get('notes', health.notes)
    
    db.commit()
    db.refresh(health)
    
    # Process symptoms string back to list
    if health.symptoms:
        health.symptoms_list = [SymptomType(s.strip()) for s in health.symptoms.split(',')]
    else:
        health.symptoms_list = []
    
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