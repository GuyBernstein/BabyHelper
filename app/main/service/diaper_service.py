from datetime import datetime
from typing import Dict, List, Union, Any, Optional

from sqlalchemy.orm import Session

from app.main.model.diaper import Diaper
from app.main.service.baby_service import get_baby_if_authorized


def create_diaper(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Diaper, Dict[str, str]]:
    """Create a new diaper record for a baby"""
    # Check if user is authorized to add diaper records for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Create new diaper record
    new_diaper = Diaper(
        created_at=datetime.utcnow(),
        time=data['time'],
        content=data['content'],
        consistency=data.get('consistency'),
        color=data.get('color'),
        notes=data.get('notes'),
        baby_id=data['baby_id']
    )

    db.add(new_diaper)
    db.commit()
    db.refresh(new_diaper)
    return new_diaper


def get_diapers_for_baby(db: Session, baby_id: int, current_user_id: int, 
                        skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None, 
                        end_date: Optional[datetime] = None) -> Union[List[Diaper], Dict[str, str]]:
    """Get diaper records for a baby with optional date filtering"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query diapers
    query = db.query(Diaper).filter(Diaper.baby_id == baby_id)
    
    # Apply date filters if provided
    if start_date:
        query = query.filter(Diaper.time >= start_date)
    if end_date:
        query = query.filter(Diaper.time <= end_date)
    
    # Order by time descending (newest first)
    query = query.order_by(Diaper.time.desc())
    
    # Apply pagination
    diapers = query.offset(skip).limit(limit).all()
    
    return diapers


def get_diaper(db: Session, diaper_id: int, current_user_id: int) -> Union[Diaper, Dict[str, str]]:
    """Get a specific diaper record by ID"""
    # Get the diaper record
    diaper = db.query(Diaper).filter(Diaper.id == diaper_id).first()
    
    if not diaper:
        return {
            'status': 'fail',
            'message': 'Diaper record not found',
        }
    
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, diaper.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby
    
    return diaper


def update_diaper(db: Session, diaper_id: int, data: Dict[str, Any], current_user_id: int) -> Union[Diaper, Dict[str, str]]:
    """Update a diaper record"""
    # Get the diaper record
    diaper = db.query(Diaper).filter(Diaper.id == diaper_id).first()
    
    if not diaper:
        return {
            'status': 'fail',
            'message': 'Diaper record not found',
        }
    
    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, diaper.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby
    
    # Update diaper record
    diaper.time = data.get('time', diaper.time)
    diaper.content = data.get('content', diaper.content)
    diaper.consistency = data.get('consistency', diaper.consistency)
    diaper.color = data.get('color', diaper.color)
    diaper.notes = data.get('notes', diaper.notes)
    
    db.commit()
    db.refresh(diaper)
    return diaper


def delete_diaper(db: Session, diaper_id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a diaper record"""
    # Get the diaper record
    diaper = db.query(Diaper).filter(Diaper.id == diaper_id).first()
    
    if not diaper:
        return {
            'status': 'fail',
            'message': 'Diaper record not found',
        }
    
    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, diaper.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby
    
    # Delete the diaper record
    db.delete(diaper)
    db.commit()
    return {'status': 'DELETED'}