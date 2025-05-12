from datetime import datetime
from typing import Optional, List
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship

from app.main import Base
from app.main.model.baby import BabyResponse


class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None
    is_active: Optional[bool] = True
    is_admin: Optional[bool] = False

class UserCreate(UserBase):
    pass

class UserUpdate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    created_at: datetime
    google_id: Optional[str] = None

    class Config:
        from_attributes = True


class UserWithBabiesResponse(UserResponse):
    babies: Annotated[List["BabyResponse"], Field(default_factory=list)]
    coparented_babies: Annotated[List["BabyResponse"], Field(default_factory=list)]

    model_config = {
        "from_attributes": True
    }

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
    is_admin = Column(Boolean, default=False)
    google_id = Column(String(255), unique=True, nullable=True, index=True)

    # Relationships
    babies = relationship("Baby", back_populates="parent")
    pumping_sessions = relationship("Pumping", back_populates="user", cascade="all, delete-orphan")
    coparented_babies = relationship("Baby", secondary="baby_coparent", back_populates="coparents")
    sent_invitations = relationship("CoParentInvitation", foreign_keys="CoParentInvitation.inviter_id", back_populates="inviter")
    received_invitations = relationship("CoParentInvitation", foreign_keys="CoParentInvitation.invitee_id", back_populates="invitee")
    notifications = relationship("Notification", back_populates="user")
    dashboard_preference = relationship("DashboardPreference", back_populates="user", uselist=False)

    def __repr__(self):
        return f"<User '{self.email}'>"