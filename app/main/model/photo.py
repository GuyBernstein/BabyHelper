from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field
from fastapi import APIRouter
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.main import Base


class PhotoType(str, Enum):
    PROFILE = "profile"
    MILESTONE = "milestone"
    GROWTH = "growth"
    OTHER = "other"


class PhotoBase(BaseModel):
    photo_type: PhotoType
    description: Optional[str] = None
    date_taken: Optional[datetime] = None


class PhotoCreate(PhotoBase):
    baby_id: int


class PhotoUpdate(PhotoBase):
    pass


class PhotoResponse(PhotoBase):
    id: int
    created_at: datetime
    baby_id: int
    url: Optional[str] = None

    class Config:
        from_attributes = True


router = APIRouter(
    prefix="/photos",
    tags=["photos"],
    responses={404: {"description": "Not found"}}
)


class Photo(Base):
    __tablename__ = "photo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    photo_type = Column(SQLEnum(PhotoType), nullable=False)
    description = Column(String(500), nullable=True)
    date_taken = Column(DateTime, nullable=True)
    s3_key = Column(String(500), nullable=False)
    
    # Foreign keys
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)
    
    # Relationships
    baby = relationship("Baby", back_populates="photos")

    def __repr__(self):
        return f"<Photo {self.photo_type} for baby {self.baby_id}>"
