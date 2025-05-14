from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.main import Base


class SleepQuality(str, Enum):
    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"


class SleepLocation(str, Enum):
    CRIB = "crib"
    BASSINET = "bassinet"
    PARENTS_ROOM = "parents_room"
    PARENTS_BED = "parents_bed"
    CAR_SEAT = "car_seat"
    STROLLER = "stroller"
    OTHER = "other"


class SleepTrainingMethod(str, Enum):
    NONE = "none"
    CRY_IT_OUT = "cry_it_out"
    FERBER = "ferber"
    CHAIR = "chair"
    PICK_UP_PUT_DOWN = "pick_up_put_down"
    BEDTIME_FADING = "bedtime_fading"
    OTHER = "other"


class SleepBase(BaseModel):
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[int] = None  # in minutes, calculated if end_time is provided
    quality: Optional[SleepQuality] = None
    location: Optional[SleepLocation] = None
    training_method: Optional[SleepTrainingMethod] = None
    notes: Optional[str] = None


class SleepCreate(SleepBase):
    baby_id: int


class SleepUpdate(SleepBase):
    pass


class SleepResponse(SleepBase):
    id: int
    created_at: datetime
    baby_id: int
    recorded_by: int
    caregiver_name: Optional[str] = None

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/sleep",
    tags=["sleep"],
    responses={404: {"description": "Not found"}}
)


class Sleep(Base):
    __tablename__ = "sleep"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)  # in minutes
    quality = Column(SQLEnum(SleepQuality), nullable=True)
    location = Column(SQLEnum(SleepLocation), nullable=True)
    training_method = Column(SQLEnum(SleepTrainingMethod), nullable=True)
    notes = Column(String(500), nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)
    recorded_by = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="sleeps")

    def __repr__(self):
        return f"<Sleep for baby {self.baby_id} from {self.start_time}>"