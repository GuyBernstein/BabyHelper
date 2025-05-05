from datetime import datetime
from typing import Dict, List, Union, Any, Optional
import uuid

from sqlalchemy.orm import Session

from app.main.model.photo import Photo, PhotoType
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

    # Generate a unique filename
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    filename = f"baby-{data['baby_id']}-{data['photo_type']}-{uuid.uuid4().hex}.{file_extension}"
    s3_key = f"{data['photo_type']}s/{filename}"

    # Read file content
    file_content = await file.read()

    # Upload to S3
    if upload_file(file_content, s3_key):
        # Create new photo record
        new_photo = Photo(
            created_at=datetime.utcnow(),
            photo_type=data['photo_type'],
            description=data.get('description'),
            date_taken=data.get('date_taken', datetime.utcnow()),
            s3_key=s3_key,
            baby_id=data['baby_id']
        )

        db.add(new_photo)
        db.commit()
        db.refresh(new_photo)
        return new_photo
    else:
        return {
            'status': 'fail',
            'message': 'Failed to upload photo'
        }


def get_baby_photos(db: Session, baby_id: int, current_user_id: int, photo_type: Optional[PhotoType] = None) -> Union[List[Dict[str, Any]], Dict[str, str]]:
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
        photo_dict = {
            'id': photo.id,
            'created_at': photo.created_at,
            'photo_type': photo.photo_type,
            'description': photo.description,
            'date_taken': photo.date_taken,
            'baby_id': photo.baby_id,
            'url': create_presigned_url(photo.s3_key)
        }
        result.append(photo_dict)
    
    return result


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
    
    # Delete the photo record
    db.delete(photo)
    db.commit()
    
    # Note: We're not deleting from S3 here
    # In a production system, you might want to implement S3 object deletion or use lifecycle policies
    
    return {'status': 'DELETED'}
