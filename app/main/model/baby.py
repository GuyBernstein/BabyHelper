from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import Column, Integer, String, DateTime, Float

# Import the Base and get_db function
from app.main import Base

# Keep your existing router
router = APIRouter(
    prefix="/baby",
    tags=["baby"],
    responses={404: {"description": "Not found"}},
)


# Add your Baby model
class Baby(Base):
    __tablename__ = "baby"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    fullname = Column(String(100), nullable=False)
    birthdate = Column(DateTime, nullable=True)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    picture = Column(String(300), nullable=True)

    # Add relationship to measurements if needed
    # measurements = relationship("Measurement", back_populates="baby")

    def __repr__(self):
        return f"<Baby '{self.fullname}'>"