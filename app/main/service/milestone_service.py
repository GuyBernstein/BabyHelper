from datetime import datetime
from typing import Dict, Union, Any, Optional, Type

from sqlalchemy.orm import Session

from app.main.model import User
from app.main.model.milestone import Milestone
from app.main.model.photo import Photo, PhotoType
from app.main.service.aws_service import create_presigned_url
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
        baby_id=data['baby_id'],
        recorded_by=current_user_id
    )

    db.add(new_milestone)
    db.commit()
    db.refresh(new_milestone)

    # If a photo_url was provided but it's not a presigned URL (just an ID or key),
    # try to find the photo and create a presigned URL
    if new_milestone.photo_url and not new_milestone.photo_url.startswith('http'):
        try:
            # Try to find photo by ID first
            photo_id = int(new_milestone.photo_url)
            photo = db.query(Photo).filter(Photo.id == photo_id, Photo.baby_id == data['baby_id']).first()

            if photo:
                # Update photo to associate with this milestone
                photo.milestone_id = new_milestone.id
                photo.photo_type = PhotoType.MILESTONE

                # Update milestone with presigned URL
                new_milestone.photo_url = create_presigned_url(photo.s3_key)
                db.commit()
        except (ValueError, TypeError):
            # Not an ID, might be an S3 key
            new_milestone.photo_url = create_presigned_url(new_milestone.photo_url)
            db.commit()

    caregiver = db.query(User).filter(User.id == new_milestone.recorded_by).first()
    if caregiver:
        new_milestone.caregiver_name = caregiver.name

    return new_milestone


def get_milestones_for_baby(db: Session, baby_id: int, current_user_id: int,
                            skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None) -> Union[dict[str, str], list[Type[Milestone]]]:
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

    # Refresh photo URLs if they exist but might be expired
    for milestone in milestones:
        # If this milestone has photos, get the first one and update the photo_url
        photos = db.query(Photo).filter(Photo.milestone_id == milestone.id).first()
        if photos and not milestone.photo_url:
            milestone.photo_url = create_presigned_url(photos.s3_key)
            db.commit()

        # Add caregiver information to each milestone record
        caregiver = db.query(User).filter(User.id == milestone.recorded_by).first()
        if caregiver:
            milestone.caregiver_name = caregiver.name

    return milestones


def get_milestone(db: Session, milestone_id: int, current_user_id: int) -> Union[
    dict[str, str], dict[str, str], Type[Milestone]]:
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

    # Refresh photo URL if it exists but might be expired
    photos = db.query(Photo).filter(Photo.milestone_id == milestone.id).first()
    if photos and not milestone.photo_url:
        milestone.photo_url = create_presigned_url(photos.s3_key)
        db.commit()

    caregiver = db.query(User).filter(User.id == milestone.recorded_by).first()
    if caregiver:
        milestone.caregiver_name = caregiver.name

    return milestone


def update_milestone(db: Session, milestone_id: int, data: Dict[str, Any], current_user_id: int) -> Union[
    dict[str, str], dict[str, str], Type[Milestone]]:
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

    # Handle photo_url update if provided
    if 'photo_url' in data:
        milestone.photo_url = data.get('photo_url')

        # If a photo_url was provided but it's not a presigned URL (just an ID or key),
        # try to find the photo and create a presigned URL
        if milestone.photo_url and not milestone.photo_url.startswith('http'):
            try:
                # Try to find photo by ID first
                photo_id = int(milestone.photo_url)
                photo = db.query(Photo).filter(Photo.id == photo_id, Photo.baby_id == milestone.baby_id).first()

                if photo:
                    # Update any existing photos to unlink them
                    db.query(Photo).filter(Photo.milestone_id == milestone.id).update({Photo.milestone_id: None})

                    # Update photo to associate with this milestone
                    photo.milestone_id = milestone.id
                    photo.photo_type = PhotoType.MILESTONE

                    # Update milestone with presigned URL
                    milestone.photo_url = create_presigned_url(photo.s3_key)
            except (ValueError, TypeError):
                # Not an ID, might be an S3 key
                milestone.photo_url = create_presigned_url(milestone.photo_url)

    db.commit()
    db.refresh(milestone)

    caregiver = db.query(User).filter(User.id == milestone.recorded_by).first()
    if caregiver:
        milestone.caregiver_name = caregiver.name

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

    # Unlink associated photos before deleting
    db.query(Photo).filter(Photo.milestone_id == milestone.id).update({
        Photo.milestone_id: None,
        Photo.photo_type: PhotoType.OTHER
    })

    # Delete the milestone record
    db.delete(milestone)
    db.commit()
    return {'status': 'DELETED'}