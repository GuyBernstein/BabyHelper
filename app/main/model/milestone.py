from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.main import Base


class MilestoneCategory(str, Enum):
    MOTOR = "motor"  # crawling, walking, etc.
    COGNITIVE = "cognitive"  # recognizing objects, problem-solving
    LANGUAGE = "language"  # first words, sentences
    SOCIAL = "social"  # smiling, playing with others
    EMOTIONAL = "emotional"  # expressing emotions
    SELF_CARE = "self_care"  # feeding, toilet training

class MilestoneBase(BaseModel):
    title: str
    category: MilestoneCategory
    description: Optional[str] = None
    typical_age_months: Optional[int] = None
    achieved_date: Optional[datetime] = None
    notes: Optional[str] = None

class MilestoneCreate(MilestoneBase):
    baby_id: int

class MilestoneUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[MilestoneCategory] = None
    description: Optional[str] = None
    typical_age_months: Optional[int] = None
    achieved_date: Optional[datetime] = None
    notes: Optional[str] = None

class MilestoneResponse(MilestoneBase):
    id: int
    created_at: datetime
    baby_id: int
    is_achieved: bool

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
    category = Column(SQLEnum(MilestoneCategory), nullable=False)
    description = Column(String(500), nullable=True)
    typical_age_months = Column(Integer, nullable=True)
    achieved_date = Column(DateTime, nullable=True)
    notes = Column(String(500), nullable=True)
    is_achieved = Column(Boolean, default=False)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="milestones")

    def __repr__(self):
        return f"<Milestone '{self.title}' for baby {self.baby_id}>"