from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Session
from app.main.model.user import User


def create_user(db: Session, data: Dict[str, Any]) -> Union[User, Dict[str, str]]:
    """Create a new user or update if exists by google_id"""
    # Check if user exists by email or google_id
    existing_user = None
    if 'email' in data:
        existing_user = db.query(User).filter(User.email == data['email']).first()

    if not existing_user and 'google_id' in data:
        existing_user = db.query(User).filter(User.google_id == data['google_id']).first()

    if not existing_user:
        # Create new user
        new_user = User(
            created_at=datetime.utcnow(),
            email=data['email'],
            name=data.get('name'),
            picture=data.get('picture'),
            google_id=data.get('google_id'),
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    else:
        # Update existing user with latest data
        existing_user.name = data.get('name', existing_user.name)
        existing_user.picture = data.get('picture', existing_user.picture)
        existing_user.google_id = data.get('google_id', existing_user.google_id)

        db.commit()
        db.refresh(existing_user)
        return existing_user


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get a user by email"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_google_id(db: Session, google_id: str) -> Optional[User]:
    """Get a user by Google ID"""
    return db.query(User).filter(User.google_id == google_id).first()


def get_all_users(db: Session) -> List[User]:
    """Get all users"""
    return db.query(User).all()


def get_user(db: Session, id: int) -> Optional[User]:
    """Get a user by ID"""
    return db.query(User).filter(User.id == id).first()