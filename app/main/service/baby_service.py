from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Session
from app.main.model.baby import Baby


def save_new_baby(db: Session, data: Dict[str, Any]) -> Union[Baby, Dict[str, str]]:
    """Create a new baby record"""
    # Check if baby with same name exists (assuming this would be a duplicate)
    existing_baby = db.query(Baby).filter(
        Baby.fullname == data['fullname'],
        Baby.birthdate == data['birthdate']
    ).first()

    if not existing_baby:
        new_baby = Baby(
            created_at=datetime.utcnow(),
            fullname=data['fullname'],
            birthdate=data.get('birthdate'),
            weight=data.get('weight'),
            height=data.get('height')
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


def update_baby(db: Session, id: int, data: Dict[str, Any]) -> Union[Baby, Dict[str, str]]:
    """Update a baby's information"""
    baby = db.query(Baby).filter(Baby.id == id).first()
    if baby:
        baby.fullname = data['fullname']
        baby.birthdate = data.get('birthdate')
        baby.weight = data.get('weight')
        baby.height = data.get('height')

        db.commit()
        db.refresh(baby)
        return baby
    else:
        response_object = {
            'status': 'fail',
            'message': 'Baby not found',
        }
        return response_object


def get_all_babies(db: Session) -> List[Baby]:
    """Get all babies"""
    return db.query(Baby).all()


def get_a_baby(db: Session, id: int) -> Optional[Baby]:
    """Get a baby by ID"""
    return db.query(Baby).filter(Baby.id == id).first()


def delete_baby(db: Session, id: int) -> Union[Dict[str, str], None]:
    """Delete a baby by ID"""
    baby = db.query(Baby).filter(Baby.id == id).first()
    if baby:
        db.delete(baby)
        db.commit()
        return {'status': 'DELETED'}
    else:
        response_object = {
            'status': 'fail',
            'message': 'Baby not found',
        }
        return response_object


def save_changes(db: Session, data: Baby) -> Baby:
    """Save changes to database"""
    db.add(data)
    db.commit()
    db.refresh(data)
    return data