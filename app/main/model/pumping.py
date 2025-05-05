from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.main import Base

class PumpingBase(BaseModel):
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[int] = None  # in minutes
    volume_left: Optional[float] = None  # in ml
    volume_right: Optional[float] = None  # in ml
    notes: Optional[str] = None

class PumpingCreate(PumpingBase):
    baby_id: int

class PumpingUpdate(PumpingBase):
    pass

class PumpingResponse(PumpingBase):
    id: int
    created_at: datetime
    baby_id: int
    total_volume: float  # Combined volume

    class Config:
        from_attributes = True

router = APIRouter(
    prefix="/pumping",
    tags=["pumping"],
    responses={404: {"description": "Not found"}}
)

class Pumping(Base):
    __tablename__ = "pumping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)  # in minutes
    volume_left = Column(Float, nullable=True)  # in ml
    volume_right = Column(Float, nullable=True)  # in ml
    notes = Column(String(500), nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="pumping_sessions")

    @property
    def total_volume(self):
        """Calculate the total volume pumped"""
        left = self.volume_left or 0
        right = self.volume_right or 0
        return left + right

    def __repr__(self):
        return f"<Pumping session for baby {self.baby_id} at {self.start_time}>"