from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Annotated

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean, Text
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

class ChecklistItemStatus(str, Enum):
    OK = "ok"
    CHECK_NEEDED = "check_needed"
    ACTION_REQUIRED = "action_required"
    NOT_TRACKED = "not_tracked"


class ChecklistItemType(str, Enum):
    FEEDING = "feeding"
    DIAPER = "diaper"
    SLEEP = "sleep"
    GAS_RELIEF = "gas_relief"
    COMFORT = "comfort"
    ENVIRONMENT = "environment"


class GasReliefStatus(str, Enum):
    BURPED = "burped"
    BICYCLE_LEGS = "bicycle_legs"
    TUMMY_MASSAGE = "tummy_massage"
    UPRIGHT_POSITION = "upright_position"
    NO_ACTION = "no_action"


class ComfortType(str, Enum):
    SKIN_TO_SKIN = "skin_to_skin"
    SWADDLING = "swaddling"
    ROCKING = "rocking"
    HOLDING = "holding"
    PACIFIER = "pacifier"
    WHITE_NOISE = "white_noise"
    SINGING = "singing"
    OTHER = "other"


class EnvironmentalFactor(str, Enum):
    TOO_BRIGHT = "too_bright"
    TOO_LOUD = "too_loud"
    TOO_HOT = "too_hot"
    TOO_COLD = "too_cold"
    TOO_STIMULATING = "too_stimulating"
    UNCOMFORTABLE_CLOTHING = "uncomfortable_clothing"
    WET_BEDDING = "wet_bedding"
    OPTIMAL = "optimal"


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


class BabyCareChecklistItem(BaseModel):
    id: str  # Using string ID to match expected event format
    type: str  # Will be "checklist_item" to differentiate from events
    time: Optional[datetime]  # Last relevant activity time
    baby_id: int
    baby_name: str
    details: Dict[str, Any]  # Contains checklist-specific data

class ChecklistItemDetails(BaseModel):
    item_type: ChecklistItemType
    status: ChecklistItemStatus
    title: str
    description: str
    last_activity_time: Optional[datetime] = None
    time_since_last: Optional[str] = None  # Human-readable time difference
    action_suggested: Optional[str] = None
    priority: int = 0  # 0 = low, 1 = medium, 2 = high

# Request/Response models for checklist tracking
class ChecklistTrackingCreate(BaseModel):
    baby_id: int
    item_type: ChecklistItemType
    status: Optional[str] = None  # Specific status based on item type
    notes: Optional[str] = None
    duration_minutes: Optional[int] = None  # For comfort tracking
    factors_adjusted: Optional[List[str]] = None  # For environmental tracking


class ChecklistTrackingResponse(BaseModel):
    id: int
    created_at: datetime
    baby_id: int
    item_type: ChecklistItemType
    recorded_by: int
    status: Optional[str] = None
    notes: Optional[str] = None
    duration_minutes: Optional[int] = None
    factors_adjusted: Optional[List[str]] = None

    class Config:
        from_attributes = True


class ChecklistHistoryResponse(BaseModel):
    baby_id: int
    item_type: ChecklistItemType
    current_status: ChecklistItemStatus
    last_tracking: Optional[ChecklistTrackingResponse] = None
    recent_history: Annotated[List[ChecklistTrackingResponse] , Field(default_factory=list)]
    insights: Annotated[Dict[str, Any] , Field(default_factory=dict)]

    model_config = {
        "from_attributes": True
    }

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

class GasReliefTracking(Base):
    __tablename__ = "gas_relief_tracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)
    recorded_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    status = Column(String(50), nullable=False)  # GasReliefStatus enum value
    effective = Column(Boolean, nullable=True)  # Whether the action helped
    notes = Column(Text, nullable=True)

    # Relationships
    baby = relationship("Baby")
    user = relationship("User")

    def __repr__(self):
        return f"<GasReliefTracking for baby {self.baby_id} at {self.created_at}>"


class ComfortTracking(Base):
    __tablename__ = "comfort_tracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)
    recorded_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    comfort_type = Column(String(50), nullable=False)  # ComfortType enum value
    duration_minutes = Column(Integer, nullable=True)
    effective = Column(Boolean, nullable=True)  # Whether the comfort method helped
    notes = Column(Text, nullable=True)

    # Relationships
    baby = relationship("Baby")
    user = relationship("User")

    def __repr__(self):
        return f"<ComfortTracking for baby {self.baby_id} at {self.created_at}>"


class EnvironmentalTracking(Base):
    __tablename__ = "environmental_tracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)
    recorded_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    factors_checked = Column(JSON, nullable=False)  # List of EnvironmentalFactor values
    factors_adjusted = Column(JSON, nullable=True)  # List of adjustments made
    room_temp = Column(Integer, nullable=True)  # Optional room temperature
    noise_level = Column(String(20), nullable=True)  # quiet, moderate, loud
    light_level = Column(String(20), nullable=True)  # dark, dim, bright
    notes = Column(Text, nullable=True)

    # Relationships
    baby = relationship("Baby")
    user = relationship("User")

    def __repr__(self):
        return f"<EnvironmentalTracking for baby {self.baby_id} at {self.created_at}>"