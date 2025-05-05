from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Column, Integer, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.main import Base


class GrowthBase(BaseModel):
    measurement_date: datetime
    weight: Optional[float] = None  # in kg
    height: Optional[float] = None  # in cm
    head_circumference: Optional[float] = None  # in cm
    notes: Optional[str] = None


class GrowthCreate(GrowthBase):
    baby_id: int


class GrowthUpdate(GrowthBase):
    pass


class GrowthResponse(GrowthBase):
    id: int
    created_at: datetime
    baby_id: int

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/growth",
    tags=["growth"],
    responses={404: {"description": "Not found"}}
)


class Growth(Base):
    __tablename__ = "growth"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    measurement_date = Column(DateTime, nullable=False)
    weight = Column(Float, nullable=True)  # in kg
    height = Column(Float, nullable=True)  # in cm
    head_circumference = Column(Float, nullable=True)  # in cm
    notes = Column(Text, nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="growth_records")

    def __repr__(self):
        return f"<Growth measurement for baby {self.baby_id} on {self.measurement_date}>"