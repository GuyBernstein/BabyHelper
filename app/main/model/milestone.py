from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field
from fastapi import APIRouter
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
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
    photo_url: Optional[str] = None


class MilestoneCreate(MilestoneBase):
    baby_id: int


class MilestoneUpdate(MilestoneBase):
    pass


class MilestoneResponse(MilestoneBase):
    id: int
    created_at: datetime
    baby_id: int

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
    photo_url = Column(String(255), nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="milestones")

    def __repr__(self):
        return f"<Milestone '{self.title}' for baby {self.baby_id}>"