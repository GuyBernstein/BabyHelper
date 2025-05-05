from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Column, Integer, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.main import Base


class PumpingBase(BaseModel):
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[int] = None  # in minutes
    left_amount: Optional[float] = None  # in ml
    right_amount: Optional[float] = None  # in ml
    total_amount: Optional[float] = None  # in ml
    notes: Optional[str] = None


class PumpingCreate(PumpingBase):
    pass


class PumpingUpdate(PumpingBase):
    pass


class PumpingResponse(PumpingBase):
    id: int
    created_at: datetime
    user_id: int

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
    left_amount = Column(Float, nullable=True)  # in ml
    right_amount = Column(Float, nullable=True)  # in ml
    total_amount = Column(Float, nullable=True)  # in ml
    notes = Column(Text, nullable=True)

    # Foreign keys
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    user = relationship("User", back_populates="pumping_sessions")

    def __repr__(self):
        return f"<Pumping session for user {self.user_id} at {self.start_time}>"