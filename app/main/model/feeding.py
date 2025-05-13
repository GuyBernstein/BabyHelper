from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
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
    PUMPING = "pumping"


class BottleContentType(str, Enum):
    FORMULA = "formula"
    BREAST_MILK = "breast_milk"
    MIXED = "mixed"


class FeedingBase(BaseModel):
    feeding_type: FeedingType
    amount: Optional[float] = None  # in ml for liquids, grams for solids
    bottle_content_type: Optional[BottleContentType] = None  # Only for bottle feeds
    duration: Optional[int] = None  # in minutes
    notes: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    last_breast: Optional[str] = None  # To track which breast was used last
    pumped_volume_left: Optional[float] = None  # For pumping sessions
    pumped_volume_right: Optional[float] = None  # For pumping sessions


class FeedingCreate(FeedingBase):
    baby_id: int


class FeedingUpdate(FeedingBase):
    pass


class FeedingResponse(FeedingBase):
    id: int
    created_at: datetime
    baby_id: int
    recorded_by: int
    caregiver_name: Optional[str] = None

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
    end_time = Column(DateTime, nullable=True)
    feeding_type = Column(SQLEnum(FeedingType), nullable=False)
    amount = Column(Float, nullable=True)  # in ml for liquids, grams for solids
    bottle_content_type = Column(SQLEnum(BottleContentType), nullable=True)
    duration = Column(Integer, nullable=True)  # in minutes
    notes = Column(String(500), nullable=True)
    last_breast = Column(String(10), nullable=True)
    pumped_volume_left = Column(Float, nullable=True)
    pumped_volume_right = Column(Float, nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)
    recorded_by = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="feedings")

    def __repr__(self):
        return f"<Feeding '{self.feeding_type}' for baby {self.baby_id}>"