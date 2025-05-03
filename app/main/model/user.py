from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter
from sqlalchemy import Column, Integer, String, DateTime, Boolean

from app.main import Base

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserUpdate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    created_at: datetime
    is_active: bool
    google_id: Optional[str] = None

    class Config:
        from_attributes = True

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}}
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    picture = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    google_id = Column(String(255), unique=True, nullable=True, index=True)

    def __repr__(self):
        return f"<User '{self.email}'>"