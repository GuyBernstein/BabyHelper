from datetime import datetime
from typing import Dict, List, Union, Any, Optional

from sqlalchemy.orm import Session

from app.main.model.sleep import Sleep
from app.main.service.baby_service import get_baby_if_authorized


def create_sleep(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Sleep, Dict[str, str]]:
    """Create a new sleep record for a baby"""
    # Check if user is authorized to add sleep records for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Calculate duration if both start and end times are provided
    duration = data.get('duration')
    if data.get('end_time') and not duration:
        # Calculate duration in minutes
        delta = data['end_time'] - data['start_time']
        duration = int(delta.total_seconds() / 60)

    # Create new sleep record
    new_sleep = Sleep(
        created_at=datetime.utcnow(),
        start_time=data['start_time'],
        end_time=data.get('end_time'),
        duration=duration,
        quality=data.get('quality'),
        notes=data.get('notes'),
        baby_id=data['baby_id']
    )

    db.add(new_sleep)
    db.commit()
    db.refresh(new_sleep)
    return new_sleep


def get_sleeps_for_baby(db: Session, baby_id: int, current_user_id: int, 
                       skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None, 
                       end_date: Optional[datetime] = None) -> Union[List[Sleep], Dict[str, str]]:
    """Get sleep records for a baby with optional date filtering"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query sleeps
    query = db.query(Sleep).filter(Sleep.baby_id == baby_id)
    
    # Apply date filters if provided
    if start_date:
        query = query.filter(Sleep.start_time >= start_date)
    if end_date:
        query = query.filter(Sleep.start_time <= end_date)
    
    # Order by time descending (newest first)
    query = query.order_by(Sleep.start_time.desc())
    
    # Apply pagination
    sleeps = query.offset(skip).limit(limit).all()
    
    return sleeps


def get_sleep(db: Session, sleep_id: int, current_user_id: int) -> Union[Sleep, Dict[str, str]]:
    """Get a specific sleep record by ID"""
    # Get the sleep record
    sleep = db.query(Sleep).filter(Sleep.id == sleep_id).first()
    
    if not sleep:
        return {
            'status': 'fail',
            'message': 'Sleep record not found',
        }
    
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, sleep.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby
    
    return sleep


def update_sleep(db: Session, sleep_id: int, data: Dict[str, Any], current_user_id: int) -> Union[Sleep, Dict[str, str]]:
    """Update a sleep record"""
    # Get the sleep record
    sleep = db.query(Sleep).filter(Sleep.id == sleep_id).first()
    
    if not sleep:
        return {
            'status': 'fail',
            'message': 'Sleep record not found',
        }
    
    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, sleep.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby
    
    # Calculate duration if end_time is updated
    start_time = data.get('start_time', sleep.start_time)
    end_time = data.get('end_time')
    duration = data.get('duration')
    
    if end_time and not duration:
        # Calculate duration in minutes
        delta = end_time - start_time
        duration = int(delta.total_seconds() / 60)
    
    # Update sleep record
    sleep.start_time = start_time
    if end_time:
        sleep.end_time = end_time
    if duration:
        sleep.duration = duration
    sleep.quality = data.get('quality', sleep.quality)
    sleep.notes = data.get('notes', sleep.notes)
    
    db.commit()
    db.refresh(sleep)
    return sleep


def delete_sleep(db: Session, sleep_id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a sleep record"""
    # Get the sleep record
    sleep = db.query(Sleep).filter(Sleep.id == sleep_id).first()
    
    if not sleep:
        return {
            'status': 'fail',
            'message': 'Sleep record not found',
        }
    
    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, sleep.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby
    
    # Delete the sleep record
    db.delete(sleep)
    db.commit()
    return {'status': 'DELETED'}