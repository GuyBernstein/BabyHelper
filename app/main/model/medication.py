from datetime import datetime, time
from enum import Enum
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Time, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.main import Base


class MedicationFrequency(str, Enum):
    ONCE = "once"
    DAILY = "daily"
    TWICE_DAILY = "twice_daily"
    THREE_TIMES_DAILY = "three_times_daily"
    FOUR_TIMES_DAILY = "four_times_daily"
    WEEKLY = "weekly"
    AS_NEEDED = "as_needed"

class MedicationBase(BaseModel):
    name: str
    dose: Optional[float] = None
    unit: Optional[str] = None  # mg, ml, etc.
    frequency: MedicationFrequency
    start_date: datetime
    end_date: Optional[datetime] = None
    time_of_day: Optional[time] = None  # For specific time medications
    notes: Optional[str] = None
    reminders: bool = True

class MedicationCreate(MedicationBase):
    baby_id: int

class MedicationUpdate(MedicationBase):
    pass

class MedicationResponse(MedicationBase):
    id: int
    created_at: datetime
    baby_id: int
    active: bool

    class Config:
        from_attributes = True

router = APIRouter(
    prefix="/medication",
    tags=["medication"],
    responses={404: {"description": "Not found"}}
)

class Medication(Base):
    __tablename__ = "medication"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    name = Column(String(100), nullable=False)
    dose = Column(Float, nullable=True)
    unit = Column(String(20), nullable=True)
    frequency = Column(SQLEnum(MedicationFrequency), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    time_of_day = Column(Time, nullable=True)
    notes = Column(String(500), nullable=True)
    reminders = Column(Boolean, default=True)
    active = Column(Boolean, default=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="medications")

    def __repr__(self):
        return f"<Medication '{self.name}' for baby {self.baby_id}>"