from datetime import datetime
from typing import Dict, List, Union, Any, Optional
import uuid

from sqlalchemy.orm import Session

from app.main.model import User
from app.main.model.photo import Photo, PhotoType
from app.main.model.milestone import Milestone
from app.main.service.baby_service import get_baby_if_authorized
from app.main.service.aws_service import upload_file, create_presigned_url


async def upload_baby_profile_picture(db: Session, baby_id: int, file, current_user_id: int) -> Dict[str, Any]:
    """Upload a profile picture for a baby"""
    # Check if user is authorized to update this baby
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Generate a unique filename
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    filename = f"baby-{baby_id}-profile-{uuid.uuid4().hex}.{file_extension}"
    s3_key = f"profiles/{filename}"

    # Read file content
    file_content = await file.read()

    # Upload to S3
    if upload_file(file_content, s3_key):
        # Update baby record with picture path
        baby.picture = s3_key
        db.commit()

        # Generate a presigned URL for immediate use
        url = create_presigned_url(s3_key)

        return {
            'status': 'success',
            'message': 'Profile picture uploaded successfully',
            'url': url
        }
    else:
        return {
            'status': 'fail',
            'message': 'Failed to upload profile picture'
        }


async def upload_baby_photo(db: Session, data: Dict[str, Any], file, current_user_id: int) -> Union[
    Photo, Dict[str, str]]:
    """Upload a photo for a baby (milestone, growth, etc.)"""
    # Check if user is authorized to add photos for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # If this is a milestone photo, verify the milestone exists and belongs to this baby
    milestone = None
    if data.get('milestone_id'):
        milestone = db.query(Milestone).filter(
            Milestone.id == data['milestone_id'],
            Milestone.baby_id == data['baby_id']
        ).first()

        if not milestone:
            return {
                'status': 'fail',
                'message': 'Milestone not found or does not belong to this baby'
            }

    # Generate a unique filename
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    filename = f"baby-{data['baby_id']}-{data['photo_type']}-{uuid.uuid4().hex}.{file_extension}"
    s3_key = f"{data['photo_type']}s/{filename}"

    # Read file content
    file_content = await file.read()

    # Upload to S3
    if not upload_file(file_content, s3_key):
        return {
            'status': 'fail',
            'message': 'Failed to upload photo'
        }

    # Create new photo record
    new_photo = Photo(
        created_at=datetime.utcnow(),
        photo_type=data['photo_type'] if not milestone else PhotoType.MILESTONE,
        description=data.get('description'),
        date_taken=data.get('date_taken', datetime.utcnow()),
        s3_key=s3_key,
        baby_id=data['baby_id'],
        milestone_id=data.get('milestone_id'),
        recorded_by=current_user_id
    )

    db.add(new_photo)
    db.commit()
    db.refresh(new_photo)

    # If associated with a milestone, update the milestone's photo_url
    if milestone:
        url = create_presigned_url(s3_key)
        milestone.photo_url = url
        db.commit()

    caregiver = db.query(User).filter(User.id == new_photo.recorded_by).first()
    if caregiver:
        new_photo.caregiver_name = caregiver.name

    return new_photo



def get_baby_photos(db: Session, baby_id: int, current_user_id: int, photo_type: Optional[PhotoType] = None) -> Union[
    List[Dict[str, Any]], Dict[str, str]]:
    """Get all photos for a baby with optional filtering by type"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query photos
    query = db.query(Photo).filter(Photo.baby_id == baby_id)

    # Filter by type if provided
    if photo_type:
        query = query.filter(Photo.photo_type == photo_type)

    # Get all matching photos
    photos = query.all()


    # Create response with presigned URLs
    result = []
    for photo in photos:
        caregiver = db.query(User).filter(User.id == photo.recorded_by).first()
        if caregiver:
            photo.caregiver_name = caregiver.name

        photo_dict = {
            'id': photo.id,
            'created_at': photo.created_at,
            'photo_type': photo.photo_type,
            'description': photo.description,
            'date_taken': photo.date_taken,
            'baby_id': photo.baby_id,
            'milestone_id': photo.milestone_id,
            'url': create_presigned_url(photo.s3_key),
            'recorded_by' : caregiver.name
        }
        result.append(photo_dict)

    return result


def get_photos_for_milestone(db: Session, milestone_id: int, current_user_id: int) -> Union[
    List[Dict[str, Any]], Dict[str, str]]:
    """Get all photos associated with a milestone"""
    # First, get the milestone to check authorization
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()

    if not milestone:
        return {
            'status': 'fail',
            'message': 'Milestone not found',
        }

    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, milestone.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query photos
    photos = db.query(Photo).filter(Photo.milestone_id == milestone_id).all()

    # Create response with presigned URLs
    result = []
    for photo in photos:
        caregiver = db.query(User).filter(User.id == photo.recorded_by).first()
        if caregiver:
            photo.caregiver_name = caregiver.name
        photo_dict = {
            'id': photo.id,
            'created_at': photo.created_at,
            'photo_type': photo.photo_type,
            'description': photo.description,
            'date_taken': photo.date_taken,
            'baby_id': photo.baby_id,
            'milestone_id': photo.milestone_id,
            'url': create_presigned_url(photo.s3_key),
            'recorded_by' : caregiver.name
        }
        result.append(photo_dict)

    return result


def link_photo_to_milestone(db: Session, photo_id: int, milestone_id: int, current_user_id: int) -> Dict[str, Any]:
    """Link an existing photo to a milestone"""
    # Get the photo
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        return {
            'status': 'fail',
            'message': 'Photo not found',
        }

    # Get the milestone
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if not milestone:
        return {
            'status': 'fail',
            'message': 'Milestone not found',
        }

    # Check if user is authorized to access both the baby for the photo and milestone
    baby = get_baby_if_authorized(db, photo.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    milestone_baby = get_baby_if_authorized(db, milestone.baby_id, current_user_id)
    if isinstance(milestone_baby, dict):  # Error response
        return milestone_baby

    # Check if photo and milestone belong to the same baby
    if photo.baby_id != milestone.baby_id:
        return {
            'status': 'fail',
            'message': 'Photo and milestone must belong to the same baby',
        }

    # Update the photo to link it to the milestone
    photo.milestone_id = milestone_id

    # If it's not already a milestone type photo, update it
    if photo.photo_type != PhotoType.MILESTONE:
        photo.photo_type = PhotoType.MILESTONE

    # Generate a presigned URL and update the milestone's photo_url
    url = create_presigned_url(photo.s3_key)
    milestone.photo_url = url

    db.commit()

    return {
        'status': 'success',
        'message': 'Photo linked to milestone successfully',
        'photo_url': url
    }


def delete_photo(db: Session, photo_id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a photo"""
    # Get the photo
    photo = db.query(Photo).filter(Photo.id == photo_id).first()

    if not photo:
        return {
            'status': 'fail',
            'message': 'Photo not found',
        }

    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, photo.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # If photo is linked to a milestone, update the milestone's photo_url to None
    if photo.milestone_id:
        milestone = db.query(Milestone).filter(Milestone.id == photo.milestone_id).first()
        if milestone:
            milestone.photo_url = None

    # Delete the photo record
    db.delete(photo)
    db.commit()

    # Note: We're not deleting from S3 here

    return {'status': 'DELETED'}