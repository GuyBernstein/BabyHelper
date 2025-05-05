from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, status, File, UploadFile, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.photo import router, PhotoType
from app.main.model.user import User
from app.main.service.aws_service import create_presigned_url
from app.main.service.oauth_service import get_current_user
from app.main.service.photo_service import (
    upload_baby_profile_picture,
    upload_baby_photo,
    get_baby_photos,
    delete_photo
)


@router.post("/profile/{baby_id}")
async def upload_profile_picture(
        baby_id: int,
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Upload a profile picture for a baby (requires authentication and parent/co-parent relationship)"""
    result = await upload_baby_profile_picture(db, baby_id, file, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to upload profile picture')
        )

    return JSONResponse(content=result)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def upload_photo(
        baby_id: int = Form(...),
        photo_type: PhotoType = Form(...),
        description: Optional[str] = Form(None),
        date_taken: Optional[datetime] = Form(None),
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Upload a photo for a baby (milestone, growth, etc.) (requires authentication and parent/co-parent relationship)"""
    data = {
        "baby_id": baby_id,
        "photo_type": photo_type,
        "description": description,
        "date_taken": date_taken or datetime.utcnow()
    }

    result = await upload_baby_photo(db, data, file, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to upload photo')
        )

    # Create response with URL
    response_data = {
        'id': result.id,
        'created_at': result.created_at,
        'baby_id': result.baby_id,
        'photo_type': result.photo_type,
        'description': result.description,
        'date_taken': result.date_taken,
        'url': create_presigned_url(result.s3_key)
    }

    return response_data


@router.get("/baby/{baby_id}")
async def get_photos_for_baby(
    baby_id: int,
    photo_type: Optional[PhotoType] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get photos for a baby with optional type filtering (requires authentication and parent/co-parent relationship)"""
    result = get_baby_photos(db, baby_id, current_user.id, photo_type)
    
    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve photos')
        )
    
    return result


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_baby_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a photo (requires authentication and parent/co-parent relationship)"""
    result = delete_photo(db, photo_id, current_user.id)
    
    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get('message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to delete photo')
        )
    
    return None
