from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field
from fastapi import APIRouter
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.main import Base


class FeedingType(str, Enum):
    BREAST_LEFT = "breast_left"
    BREAST_RIGHT = "breast_right"
    BREAST_BOTH = "breast_both"
    BOTTLE = "bottle"
    FORMULA = "formula"
    SOLIDS = "solids"


class FeedingBase(BaseModel):
    feeding_type: FeedingType
    amount: Optional[float] = None  # in ml for liquids, grams for solids
    duration: Optional[int] = None  # in minutes
    notes: Optional[str] = None
    start_time: datetime


class FeedingCreate(FeedingBase):
    baby_id: int


class FeedingUpdate(FeedingBase):
    pass


class FeedingResponse(FeedingBase):
    id: int
    created_at: datetime
    baby_id: int

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/feeding",
    tags=["feeding"],
    responses={404: {"description": "Not found"}}
)


class Feeding(Base):
    __tablename__ = "feeding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    start_time = Column(DateTime, nullable=False)
    feeding_type = Column(SQLEnum(FeedingType), nullable=False)
    amount = Column(Float, nullable=True)  # in ml for liquids, grams for solids
    duration = Column(Integer, nullable=True)  # in minutes
    notes = Column(String(500), nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="feedings")

    def __repr__(self):
        return f"<Feeding '{self.feeding_type}' for baby {self.baby_id}>"
