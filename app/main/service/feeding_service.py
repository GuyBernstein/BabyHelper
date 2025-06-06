from datetime import datetime
from typing import Dict, Union, Any, Optional, Type

from sqlalchemy.orm import Session

from app.main.model import User
from app.main.model.feeding import Feeding
from app.main.service.baby_service import get_baby_if_authorized


def create_feeding(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Feeding, Dict[str, str]]:
    """Create a new feeding record for a baby"""
    # Check if user is authorized to add feedings for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Calculate duration if both start and end times are provided
    duration = data.get('duration')
    if data.get('end_time') and not duration:
        # Calculate duration in minutes
        delta = data['end_time'] - data['start_time']
        duration = int(delta.total_seconds() / 60)

    # Create new feeding record
    new_feeding = Feeding(
        created_at=datetime.utcnow(),
        start_time=data['start_time'],
        end_time=data.get('end_time'),
        feeding_type=data['feeding_type'],
        amount=data.get('amount'),
        duration=duration,
        notes=data.get('notes'),
        baby_id=data['baby_id'],
        recorded_by = current_user_id
    )

    db.add(new_feeding)
    db.commit()
    db.refresh(new_feeding)

    caregiver = db.query(User).filter(User.id == new_feeding.recorded_by).first()
    if caregiver:
        new_feeding.caregiver_name = caregiver.name
    return new_feeding


def get_feedings_for_baby(db: Session, baby_id: int, current_user_id: int, 
                        skip: int = 0, limit: int = None, start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> Union[dict[str, str], list[Type[Feeding]]]:
    """Get feeding records for a baby with optional date filtering"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query feedings
    query = db.query(Feeding).filter(Feeding.baby_id == baby_id)
    
    # Apply date filters if provided
    if start_date:
        query = query.filter(Feeding.start_time >= start_date)
    if end_date:
        query = query.filter(Feeding.start_time <= end_date)
    
    # Order by time descending (newest first)
    query = query.order_by(Feeding.start_time.desc())
    
    # Apply pagination
    if limit:
        feedings = query.offset(skip).limit(limit).all()
    else:
        feedings = query.all()
    # Add caregiver information to each feeding record
    for feeding in feedings:
        caregiver = db.query(User).filter(User.id == feeding.recorded_by).first()
        if caregiver:
            feeding.caregiver_name = caregiver.name
    
    return feedings


def get_feeding(db: Session, feeding_id: int, current_user_id: int) -> Union[
    dict[str, str], dict[str, str], Type[Feeding]]:
    """Get a specific feeding record by ID"""
    # Get the feeding
    feeding = db.query(Feeding).filter(Feeding.id == feeding_id).first()
    
    if not feeding:
        return {
            'status': 'fail',
            'message': 'Feeding record not found',
        }
    
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, feeding.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    caregiver = db.query(User).filter(User.id == feeding.recorded_by).first()
    if caregiver:
        feeding.caregiver_name = caregiver.name
    
    return feeding


def update_feeding(db: Session, feeding_id: int, data: Dict[str, Any], current_user_id: int) -> Union[
    dict[str, str], dict[str, str], Type[Feeding]]:
    """Update a feeding record"""
    # Get the feeding
    feeding = db.query(Feeding).filter(Feeding.id == feeding_id).first()
    
    if not feeding:
        return {
            'status': 'fail',
            'message': 'Feeding record not found',
        }
    
    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, feeding.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby
    
    # Update feeding record
    feeding.start_time = data.get('start_time', feeding.start_time)
    feeding.feeding_type = data.get('feeding_type', feeding.feeding_type)
    feeding.amount = data.get('amount', feeding.amount)
    feeding.duration = data.get('duration', feeding.duration)
    feeding.notes = data.get('notes', feeding.notes)
    
    db.commit()
    db.refresh(feeding)

    caregiver = db.query(User).filter(User.id == feeding.recorded_by).first()
    if caregiver:
        feeding.caregiver_name = caregiver.name

    return feeding


def delete_feeding(db: Session, feeding_id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a feeding record"""
    # Get the feeding
    feeding = db.query(Feeding).filter(Feeding.id == feeding_id).first()
    
    if not feeding:
        return {
            'status': 'fail',
            'message': 'Feeding record not found',
        }
    
    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, feeding.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby
    
    # Delete the feeding
    db.delete(feeding)
    db.commit()
    return {'status': 'DELETED'}