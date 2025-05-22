from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.main import Base


class MilestoneCategory(str, Enum):
    MOTOR = "motor"
    COGNITIVE = "cognitive"
    SOCIAL = "social"
    LANGUAGE = "language"
    EMOTIONAL = "emotional"
    OTHER = "other"


class MilestoneBase(BaseModel):
    title: str
    category: MilestoneCategory
    achieved_date: datetime
    description: Optional[str] = None
    notes: Optional[str] = None


class MilestoneCreate(MilestoneBase):
    baby_id: int


class MilestoneUpdate(MilestoneBase):
    pass


class MilestoneResponse(MilestoneBase):
    id: int
    created_at: datetime
    baby_id: int
    recorded_by: int
    caregiver_name: Optional[str] = None

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/milestone",
    tags=["milestone"],
    responses={404: {"description": "Not found"}}
)


class Milestone(Base):
    __tablename__ = "milestone"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    title = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    achieved_date = Column(DateTime, nullable=False)
    description = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    photo_url = Column(String(500), nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)
    recorded_by = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="milestones")
    photos = relationship("Photo", back_populates="milestone", cascade="all, delete-orphan")  # New relationship

    def __repr__(self):
        return f"<Milestone '{self.title}' for baby {self.baby_id}>"