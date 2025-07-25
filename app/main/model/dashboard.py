from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship

from app.main import Base


class WidgetType(str, Enum):
    UPCOMING_EVENTS = "upcoming_events"
    RECENT_ACTIVITIES = "recent_activities"
    CARE_METRICS = "care_metrics"
    FEEDING_STATS = "feeding_stats"
    SLEEP_PATTERNS = "sleep_patterns"
    GROWTH_CHART = "growth_chart"
    MILESTONE_TIMELINE = "milestone_timeline"
    PHOTO_GALLERY = "photo_gallery"


class TimeFrame(str, Enum):
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    CUSTOM = "custom"


class WidgetConfig(BaseModel):
    type: WidgetType
    position: int
    enabled: bool = True
    timeframe: TimeFrame = TimeFrame.WEEK
    custom_settings: Optional[Dict[str, Any]] = None  # Can include custom_start_date and custom_end_date


class DashboardPreferenceBase(BaseModel):
    layout_type: str = "grid"  # grid, list, etc.
    default_baby_id: Optional[int] = None
    default_timeframe: TimeFrame = TimeFrame.WEEK
    widgets_config: List[Dict[str, Any]]
    custom_start_date: Optional[datetime] = None
    custom_end_date: Optional[datetime] = None

class DashboardPreferenceCreate(DashboardPreferenceBase):
    pass

class DashboardPreferenceUpdate(DashboardPreferenceBase):
    pass

class DashboardPreferenceResponse(DashboardPreferenceBase):
    id: int
    created_at: datetime
    user_id: int

    class Config:
        from_attributes = True


# API Router
router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    responses={404: {"description": "Not found"}}
)


class DashboardPreference(Base):
    __tablename__ = "dashboard_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    layout_type = Column(String(50), nullable=False, default="grid")
    default_baby_id = Column(Integer, ForeignKey('baby.id'), nullable=True)
    default_timeframe = Column(String(20), nullable=False, default="week")
    widgets_config = Column(JSON, nullable=False)
    custom_start_date = Column(DateTime, nullable=True)
    custom_end_date = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="dashboard_preference")
    default_baby = relationship("Baby")

    def __repr__(self):
        return f"<DashboardPreference for user {self.user_id}>"