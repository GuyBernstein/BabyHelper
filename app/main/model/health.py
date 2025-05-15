from datetime import datetime
from typing import Optional, List, Annotated
from enum import Enum
from pydantic import BaseModel, Field
from fastapi import APIRouter
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.main import Base


class SymptomType(str, Enum):
    FEVER = "fever"
    COUGH = "cough"
    CONGESTION = "congestion"
    RASH = "rash"
    VOMITING = "vomiting"
    DIARRHEA = "diarrhea"
    CONSTIPATION = "constipation"
    IRRITABILITY = "irritability"
    LETHARGY = "lethargy"
    OTHER = "other"


class MedicationType(str, Enum):
    ACETAMINOPHEN = "acetaminophen"  # Tylenol
    IBUPROFEN = "ibuprofen"          # Motrin/Advil
    ANTIBIOTIC = "antibiotic"
    ANTIHISTAMINE = "antihistamine"
    OTHER = "other"


class HealthBase(BaseModel):
    time: datetime
    temperature: Optional[float] = None  # in Celsius
    symptoms: Annotated[Optional[List[SymptomType]], Field(default_factory=list)]
    medication: Optional[MedicationType] = None
    medication_dose: Optional[float] = None  # in ml or mg
    notes: Optional[str] = None

    model_config = {
        "from_attributes": True
    }

class HealthCreate(HealthBase):
    baby_id: int


class HealthUpdate(HealthBase):
    pass


class HealthResponse(HealthBase):
    id: int
    created_at: datetime
    baby_id: int
    recorded_by: int
    caregiver_name: Optional[str] = None

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/health",
    tags=["health"],
    responses={404: {"description": "Not found"}}
)


class Health(Base):
    __tablename__ = "health"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    time = Column(DateTime, nullable=False)
    temperature = Column(Float, nullable=True)  # in Celsius
    symptoms = Column(String(500), nullable=True)  # Store as comma-separated values
    medication = Column(SQLEnum(MedicationType), nullable=True)
    medication_dose = Column(Float, nullable=True)  # in ml or mg
    notes = Column(String(500), nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)
    recorded_by = Column(Integer, ForeignKey('users.id'), nullable=False)


    # Relationships
    baby = relationship("Baby", back_populates="health_records")

    def __repr__(self):
        return f"<Health record for baby {self.baby_id} at {self.time}>"
