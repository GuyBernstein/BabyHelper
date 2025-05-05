from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.main import Base


class DoctorVisitBase(BaseModel):
    visit_date: datetime
    doctor_name: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    follow_up_date: Optional[datetime] = None

class DoctorVisitCreate(DoctorVisitBase):
    baby_id: int

class DoctorVisitUpdate(DoctorVisitBase):
    pass

class DoctorVisitResponse(DoctorVisitBase):
    id: int
    created_at: datetime
    baby_id: int

    class Config:
        from_attributes = True

router = APIRouter(
    prefix="/doctorvisit",
    tags=["doctor visit"],
    responses={404: {"description": "Not found"}}
)

class DoctorVisit(Base):
    __tablename__ = "doctor_visit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    visit_date = Column(DateTime, nullable=False)
    doctor_name = Column(String(100), nullable=False)
    reason = Column(String(255), nullable=True)
    notes = Column(String(1000), nullable=True)
    follow_up_date = Column(DateTime, nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="doctor_visits")

    def __repr__(self):
        return f"<DoctorVisit for baby {self.baby_id} on {self.visit_date}>"