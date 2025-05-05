from datetime import datetime
from typing import Dict, List, Union, Any, Optional

from sqlalchemy.orm import Session

from app.main.model.milestone import Milestone
from app.main.service.baby_service import get_baby_if_authorized


def create_milestone(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Milestone, Dict[str, str]]:
    """Create a new developmental milestone record for a baby"""
    # Check if user is authorized to add milestone records for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Create new milestone record
    new_milestone = Milestone(
        created_at=datetime.utcnow(),
        title=data['title'],
        category=data['category'],
        achieved_date=data['achieved_date'],
        description=data.get('description'),
        notes=data.get('notes'),
        photo_url=data.get('photo_url'),
        baby_id=data['baby_id']
    )

    db.add(new_milestone)
    db.commit()
    db.refresh(new_milestone)
    return new_milestone


def get_milestones_for_baby(db: Session, baby_id: int, current_user_id: int,
                            skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None) -> Union[List[Milestone], Dict[str, str]]:
    """Get developmental milestone records for a baby with optional date filtering"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query milestones
    query = db.query(Milestone).filter(Milestone.baby_id == baby_id)

    # Apply date filters if provided
    if start_date:
        query = query.filter(Milestone.achieved_date >= start_date)
    if end_date:
        query = query.filter(Milestone.achieved_date <= end_date)

    # Order by date descending (newest first)
    query = query.order_by(Milestone.achieved_date.desc())

    # Apply pagination
    milestones = query.offset(skip).limit(limit).all()

    return milestones


def get_milestone(db: Session, milestone_id: int, current_user_id: int) -> Union[Milestone, Dict[str, str]]:
    """Get a specific developmental milestone record by ID"""
    # Get the milestone record
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()

    if not milestone:
        return {
            'status': 'fail',
            'message': 'Milestone record not found',
        }

    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, milestone.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    return milestone


def update_milestone(db: Session, milestone_id: int, data: Dict[str, Any], current_user_id: int) -> Union[
    Milestone, Dict[str, str]]:
    """Update a developmental milestone record"""
    # Get the milestone record
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()

    if not milestone:
        return {
            'status': 'fail',
            'message': 'Milestone record not found',
        }

    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, milestone.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Update milestone record
    milestone.title = data.get('title', milestone.title)
    milestone.category = data.get('category', milestone.category)
    milestone.achieved_date = data.get('achieved_date', milestone.achieved_date)
    milestone.description = data.get('description', milestone.description)
    milestone.notes = data.get('notes', milestone.notes)
    milestone.photo_url = data.get('photo_url', milestone.photo_url)

    db.commit()
    db.refresh(milestone)
    return milestone


def delete_milestone(db: Session, milestone_id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a developmental milestone record"""
    # Get the milestone record
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()

    if not milestone:
        return {
            'status': 'fail',
            'message': 'Milestone record not found',
        }

    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, milestone.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Delete the milestone record
    db.delete(milestone)
    db.commit()
    return {'status': 'DELETED'}