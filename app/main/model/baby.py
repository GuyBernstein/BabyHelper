from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter
from sqlalchemy import Column, Integer, String, DateTime, Float

from app.main import Base

class BabyBase(BaseModel):
    fullname: str
    birthdate: Optional[datetime] = None
    weight: Optional[float] = None
    height: Optional[float] = None

class BabyCreate(BabyBase):
    pass

class BabyUpdate(BabyBase):
    pass

class BabyResponse(BabyBase):
    id: int
    created_at: datetime
    picture: Optional[str] = None

    class Config:
        from_attributes = True

router = APIRouter(
    prefix="/baby",
    tags=["baby"],
    responses={404: {"description": "Not found"}}
)

class Baby(Base):
    __tablename__ = "baby"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    fullname = Column(String(100), nullable=False)
    birthdate = Column(DateTime, nullable=True)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    picture = Column(String(300), nullable=True)

    def __repr__(self):
        return f"<Baby '{self.fullname}'>"