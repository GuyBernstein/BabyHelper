from datetime import datetime
from typing import Dict, List, Union, Any, Optional

from sqlalchemy.orm import Session

from app.main.model.pumping import Pumping


def create_pumping(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Pumping, Dict[str, str]]:
    """Create a new pumping session record for a user"""
    # Calculate duration if both start and end times are provided
    duration = data.get('duration')
    if data.get('end_time') and not duration:
        # Calculate duration in minutes
        delta = data['end_time'] - data['start_time']
        duration = int(delta.total_seconds() / 60)

    # Calculate total amount if left and right amounts are provided
    total_amount = data.get('total_amount')
    if data.get('left_amount') is not None and data.get('right_amount') is not None and total_amount is None:
        total_amount = data.get('left_amount', 0) + data.get('right_amount', 0)

    # Create new pumping record
    new_pumping = Pumping(
        created_at=datetime.utcnow(),
        start_time=data['start_time'],
        end_time=data.get('end_time'),
        duration=duration,
        left_amount=data.get('left_amount'),
        right_amount=data.get('right_amount'),
        total_amount=total_amount,
        notes=data.get('notes'),
        user_id=current_user_id
    )

    db.add(new_pumping)
    db.commit()
    db.refresh(new_pumping)
    return new_pumping


def get_pumpings_for_user(db: Session, user_id: int,
                          skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> List[Pumping]:
    """Get pumping session records for a user with optional date filtering"""
    # Query pumping sessions
    query = db.query(Pumping).filter(Pumping.user_id == user_id)

    # Apply date filters if provided
    if start_date:
        query = query.filter(Pumping.start_time >= start_date)
    if end_date:
        query = query.filter(Pumping.start_time <= end_date)

    # Order by time descending (newest first)
    query = query.order_by(Pumping.start_time.desc())

    # Apply pagination
    pumpings = query.offset(skip).limit(limit).all()

    return pumpings


def get_pumping(db: Session, pumping_id: int, current_user_id: int) -> Union[Pumping, Dict[str, str]]:
    """Get a specific pumping session record by ID"""
    # Get the pumping record
    pumping = db.query(Pumping).filter(Pumping.id == pumping_id).first()

    if not pumping:
        return {
            'status': 'fail',
            'message': 'Pumping session record not found',
        }

    # Check if user owns this pumping record
    if pumping.user_id != current_user_id:
        return {
            'status': 'fail',
            'message': 'Not authorized to access this pumping record',
        }

    return pumping


def update_pumping(db: Session, pumping_id: int, data: Dict[str, Any], current_user_id: int) -> Union[
    Pumping, Dict[str, str]]:
    """Update a pumping session record"""
    # Get the pumping record
    pumping = db.query(Pumping).filter(Pumping.id == pumping_id).first()

    if not pumping:
        return {
            'status': 'fail',
            'message': 'Pumping session record not found',
        }

    # Check if user owns this pumping record
    if pumping.user_id != current_user_id:
        return {
            'status': 'fail',
            'message': 'Not authorized to access this pumping record',
        }

    # Calculate duration if end_time is updated
    start_time = data.get('start_time', pumping.start_time)
    end_time = data.get('end_time')
    duration = data.get('duration')

    if end_time and not duration:
        # Calculate duration in minutes
        delta = end_time - start_time
        duration = int(delta.total_seconds() / 60)

    # Calculate total amount if left and right amounts are updated
    left_amount = data.get('left_amount')
    right_amount = data.get('right_amount')
    total_amount = data.get('total_amount')

    if left_amount is not None and right_amount is not None and total_amount is None:
        total_amount = left_amount + right_amount

    # Update pumping record
    pumping.start_time = start_time
    if end_time:
        pumping.end_time = end_time
    if duration:
        pumping.duration = duration
    if left_amount is not None:
        pumping.left_amount = left_amount
    if right_amount is not None:
        pumping.right_amount = right_amount
    if total_amount is not None:
        pumping.total_amount = total_amount
    pumping.notes = data.get('notes', pumping.notes)

    db.commit()
    db.refresh(pumping)
    return pumping


def delete_pumping(db: Session, pumping_id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a pumping session record"""
    # Get the pumping record
    pumping = db.query(Pumping).filter(Pumping.id == pumping_id).first()

    if not pumping:
        return {
            'status': 'fail',
            'message': 'Pumping session record not found',
        }

    # Check if user owns this pumping record
    if pumping.user_id != current_user_id:
        return {
            'status': 'fail',
            'message': 'Not authorized to access this pumping record',
        }

    # Delete the pumping record
    db.delete(pumping)
    db.commit()
    return {'status': 'DELETED'}