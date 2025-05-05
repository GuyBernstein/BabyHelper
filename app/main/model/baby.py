from datetime import datetime
from typing import Optional, List, Annotated
from pydantic import BaseModel, Field
from fastapi import APIRouter
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.main import Base


class BabyBase(BaseModel):
    fullname: str
    birthdate: Optional[datetime] = None
    weight: Optional[float] = None
    height: Optional[float] = None


class BabyCreate(BabyBase):
    pass


class BabyUpdate(BabyBase):
    pass


class ParentInfo(BaseModel):
    id: int
    name: Optional[str] = None
    email: str
    picture: Optional[str] = None

    class Config:
        from_attributes = True


class BabyResponse(BabyBase):
    id: int
    created_at: datetime
    picture: Optional[str] = None
    picture_url: Optional[str] = None  # Field for presigned URL to the picture
    parent_id: int
    parent: Optional[ParentInfo] = None
    coparents: Annotated[List[ParentInfo], Field(default_factory=list)]

    model_config = {
        "from_attributes": True
    }


router = APIRouter(
    prefix="/baby",
    tags=["baby"],
    responses={404: {"description": "Not found"}}
)


class Baby(Base):
    __tablename__ = "baby"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    fullname = Column(String(100), nullable=False)
    birthdate = Column(DateTime, nullable=True)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    picture = Column(String(300), nullable=True)

    # Foreign keys
    parent_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    parent = relationship("User", back_populates="babies")
    coparents = relationship("User", secondary="baby_coparent", back_populates="coparented_babies")
    invitations = relationship("CoParentInvitation", back_populates="baby")

    # relationships for tracking categories
    feedings = relationship("Feeding", back_populates="baby", cascade="all, delete-orphan")
    sleeps = relationship("Sleep", back_populates="baby", cascade="all, delete-orphan")
    diapers = relationship("Diaper", back_populates="baby", cascade="all, delete-orphan")
    health_records = relationship("Health", back_populates="baby", cascade="all, delete-orphan")
    doctor_visits = relationship("DoctorVisit", back_populates="baby", cascade="all, delete-orphan")
    growth_records = relationship("Growth", back_populates="baby", cascade="all, delete-orphan")
    medications = relationship("Medication", back_populates="baby", cascade="all, delete-orphan")
    milestones = relationship("Milestone", back_populates="baby", cascade="all, delete-orphan")
    photos = relationship("Photo", back_populates="baby", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Baby '{self.fullname}'>"