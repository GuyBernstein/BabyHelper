from datetime import datetime
from typing import Dict, List, Any, Union

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.main.model.baby import Baby
from app.main.model.user import User
from app.main.service.aws_service import create_presigned_url


def save_new_baby(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Baby, Dict[str, str]]:
    """Create a new baby record with parent relationship"""
    # Check if baby with same name exists for this user (assuming this would be a duplicate)
    existing_baby = db.query(Baby).filter(
        Baby.fullname == data['fullname'],
        Baby.birthdate == data.get('birthdate'),
        Baby.parent_id == current_user_id
    ).first()

    if not existing_baby:
        new_baby = Baby(
            created_at=datetime.utcnow(),
            fullname=data['fullname'],
            birthdate=data.get('birthdate'),
            weight=data.get('weight'),
            height=data.get('height'),
            picture=data.get('picture'),
            parent_id=current_user_id,
            sex=data.get('sex')
        )
        db.add(new_baby)
        db.commit()
        db.refresh(new_baby)
        return new_baby
    else:
        response_object = {
            'status': 'fail',
            'message': 'Baby already exists',
        }
        return response_object


def update_baby(db: Session, id: int, data: Dict[str, Any], current_user_id: int) -> Union[Baby, Dict[str, str]]:
    """Update a baby's information if the user is a parent or co-parent"""
    baby = get_baby_if_authorized(db, id, current_user_id)

    if isinstance(baby, dict):  # Error response
        return baby

    baby.fullname = data['fullname']
    baby.birthdate = data.get('birthdate')
    baby.weight = data.get('weight')
    baby.height = data.get('height')
    baby.sex = data.get('sex')
    if data.get('picture'):
        baby.picture = data.get('picture')

    db.commit()
    db.refresh(baby)
    return baby


def get_all_babies_for_user(db: Session, user_id: int) -> List[Baby]:
    """Get all babies for a specific user (as parent or co-parent)"""
    # Get babies where user is the primary parent
    parent_babies = db.query(Baby).filter(Baby.parent_id == user_id).all()

    # Get babies where user is a co-parent
    user = db.query(User).filter(User.id == user_id).first()
    coparent_babies = user.coparented_babies if user else []

    # Combine both lists (avoiding duplicates)
    all_babies = list(parent_babies)
    for baby in coparent_babies:
        if baby not in all_babies:
            all_babies.append(baby)

    # Add presigned URLs for pictures
    for baby in all_babies:
        if baby.picture:
            baby.picture_url = create_presigned_url(baby.picture)

    return all_babies


def get_baby_if_authorized(db: Session, baby_id: int, user_id: int) -> Union[Baby, Dict[str, str]]:
    """Get a baby by ID if the user is authorized (parent or co-parent)"""
    baby = db.query(Baby).filter(Baby.id == baby_id).first()

    if not baby:
        return {
            'status': 'fail',
            'message': 'Baby not found',
        }

    # Check if user is the primary parent
    if baby.parent_id == user_id:
        # Add presigned URL for picture if exists
        if baby.picture:
            baby.picture_url = create_presigned_url(baby.picture)
        return baby

    # Check if user is a co-parent
    for coparent in baby.coparents:
        if coparent.id == user_id:
            # Add presigned URL for picture if exists
            if baby.picture:
                baby.picture_url = create_presigned_url(baby.picture)
            return baby

    # User is not authorized
    return {
        'status': 'fail',
        'message': 'Not authorized to access this baby',
    }

def get_a_baby(db: Session, id: int, current_user_id: int) -> Union[Baby, Dict[str, str]]:
    """Get a baby by ID if the user is authorized"""
    return get_baby_if_authorized(db, id, current_user_id)


def delete_baby(db: Session, id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a baby by ID if the user is the primary parent"""
    baby = db.query(Baby).filter(Baby.id == id).first()

    if not baby:
        return {
            'status': 'fail',
            'message': 'Baby not found',
        }

    # Only the primary parent can delete a baby
    if baby.parent_id != current_user_id:
        return {
            'status': 'fail',
            'message': 'Only the primary parent can delete a baby',
        }

    db.delete(baby)
    db.commit()
    return {'status': 'DELETED'}

def _get_baby_ids(db, user_id, baby_id):
    if baby_id is not None:
        # Verify user has access to this baby
        baby = get_baby_if_authorized(db, baby_id, user_id)
        if isinstance(baby, dict):  # Error response
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=baby.get('message', 'Unauthorized')
            )
        return [baby_id]
    else:
        # Get all babies the user has access to
        babies = get_all_babies_for_user(db, user_id)
        return [baby.id for baby in babies]