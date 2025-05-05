from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.main import Base


class MedicationRoute(str, Enum):
    ORAL = "oral"
    TOPICAL = "topical"
    DROPS = "drops"
    INJECTION = "injection"
    INHALED = "inhaled"
    RECTAL = "rectal"
    OTHER = "other"


class MedicationBase(BaseModel):
    name: str
    dosage: float
    dosage_unit: str  # mg, ml, etc.
    route: MedicationRoute
    time_given: datetime
    given_by: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


class MedicationCreate(MedicationBase):
    baby_id: int


class MedicationUpdate(MedicationBase):
    pass


class MedicationResponse(MedicationBase):
    id: int
    created_at: datetime
    baby_id: int

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
    dosage = Column(Float, nullable=False)
    dosage_unit = Column(String(20), nullable=False)
    route = Column(String(20), nullable=False)
    time_given = Column(DateTime, nullable=False)
    given_by = Column(String(100), nullable=True)
    reason = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="medications")

    def __repr__(self):
        return f"<Medication {self.name} for baby {self.baby_id} at {self.time_given}>"