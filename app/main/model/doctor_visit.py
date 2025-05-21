from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.main import Base


class VisitType(str, Enum):
    CHECKUP = "checkup"
    SICK_VISIT = "sick_visit"
    VACCINATION = "vaccination"
    SPECIALIST = "specialist"
    EMERGENCY = "emergency"
    OTHER = "other"


class DoctorVisitBase(BaseModel):
    visit_date: datetime
    doctor_name: str
    visit_type: VisitType
    reason: Optional[str] = None
    diagnosis: Optional[str] = None
    treatment: Optional[str] = None
    notes: Optional[str] = None
    next_appointment: Optional[datetime] = None


class DoctorVisitCreate(DoctorVisitBase):
    baby_id: int


class DoctorVisitUpdate(DoctorVisitBase):
    pass


class DoctorVisitResponse(DoctorVisitBase):
    id: int
    created_at: datetime
    baby_id: int
    recorded_by: int
    caregiver_name: Optional[str] = None

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/doctor-visit",
    tags=["doctor_visit"],
    responses={404: {"description": "Not found"}}
)


class DoctorVisit(Base):
    __tablename__ = "doctor_visit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    visit_date = Column(DateTime, nullable=False)
    doctor_name = Column(String(100), nullable=False)
    visit_type = Column(String(50), nullable=False)
    reason = Column(String(500), nullable=True)
    diagnosis = Column(String(500), nullable=True)
    treatment = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    next_appointment = Column(DateTime, nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)
    recorded_by = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="doctor_visits")

    def __repr__(self):
        return f"<DoctorVisit for baby {self.baby_id} on {self.visit_date}>"