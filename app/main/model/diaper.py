from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field
from fastapi import APIRouter
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.main import Base


class DiaperContent(str, Enum):
    WET = "wet"
    DIRTY = "dirty"
    BOTH = "both"
    DRY = "dry"


class DiaperConsistency(str, Enum):
    SOLID = "solid"
    SOFT = "soft"
    LOOSE = "loose"
    WATERY = "watery"
    MUCOUSY = "mucousy"
    SEEDY = "seedy"


class DiaperColor(str, Enum):
    YELLOW = "yellow"
    GREEN = "green"
    BROWN = "brown"
    BLACK = "black"
    RED = "red"
    WHITE = "white"


class DiaperBase(BaseModel):
    time: datetime
    content: DiaperContent
    consistency: Optional[DiaperConsistency] = None
    color: Optional[DiaperColor] = None
    notes: Optional[str] = None


class DiaperCreate(DiaperBase):
    baby_id: int


class DiaperUpdate(DiaperBase):
    pass


class DiaperResponse(DiaperBase):
    id: int
    created_at: datetime
    baby_id: int

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/diaper",
    tags=["diaper"],
    responses={404: {"description": "Not found"}}
)


class Diaper(Base):
    __tablename__ = "diaper"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    time = Column(DateTime, nullable=False)
    content = Column(SQLEnum(DiaperContent), nullable=False)
    consistency = Column(SQLEnum(DiaperConsistency), nullable=True)
    color = Column(SQLEnum(DiaperColor), nullable=True)
    notes = Column(String(500), nullable=True)

    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)

    # Relationships
    baby = relationship("Baby", back_populates="diapers")

    def __repr__(self):
        return f"<Diaper {self.content} for baby {self.baby_id} at {self.time}>"
