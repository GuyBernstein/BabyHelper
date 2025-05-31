"""
Tool model for data extraction and Claude API integration.
Designed to extract data from dashboard summaries and provide
structured data to Claude API for processing user requests.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, Annotated

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.main import Base


class ToolType(str, Enum):
    """Available tool types that can be used for data extraction"""
    ACTIVITY_ANALYZER = "activity_analyzer"
    SLEEP_PATTERN_ANALYZER = "sleep_pattern_analyzer"
    FEEDING_TRACKER = "feeding_tracker"
    HEALTH_MONITOR = "health_monitor"
    GROWTH_TRACKER = "growth_tracker"
    MILESTONE_TRACKER = "milestone_tracker"
    CARE_METRICS_ANALYZER = "care_metrics_analyzer"
    SCHEDULE_ASSISTANT = "schedule_assistant"


class ToolStatus(str, Enum):
    """Tool availability status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class ToolBase(BaseModel):
    """Base schema for Tool"""
    name: str = Field(..., description="Tool name")
    tool_type: ToolType = Field(..., description="Type of tool")
    description: str = Field(..., description="Tool description")
    version: str = Field(default="1.0.0", description="Tool version")
    capabilities: Annotated[Dict[str, Any], Field(default_factory=dict, description="Tool capabilities")]
    configuration: Annotated[Dict[str, Any], Field(default_factory=dict, description="Tool configuration")]
    status: ToolStatus = Field(default=ToolStatus.ACTIVE, description="Tool status")

    model_config = {
        "from_attributes": True
    }

class ToolCreate(ToolBase):
    """Schema for creating a new tool"""
    pass


class ToolUpdate(BaseModel):
    """Schema for updating a tool"""
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    configuration: Optional[Dict[str, Any]] = None
    status: Optional[ToolStatus] = None


class ToolResponse(ToolBase):
    """Schema for tool response"""
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool
    usage_count: int = 0

    class Config:
        from_attributes = True


class ToolExecutionRequest(BaseModel):
    """Schema for tool execution request"""
    tool_id: int
    baby_id: Optional[int] = None
    parameters: Annotated[Dict[str, Any], Field(default_factory=dict)]
    context: Annotated[Optional[Dict[str, Any]], Field(default_factory=dict)]

    model_config = {
        "from_attributes": True
    }

class ToolExecutionResponse(BaseModel):
    """Schema for tool execution response"""
    tool_id: int
    execution_id: str
    status: str
    data: Dict[str, Any]
    execution_metadata: Annotated[Dict[str, Any], Field(default_factory=dict)]
    execution_time_ms: float

    model_config = {
        "from_attributes": True
    }

# API Router
router = APIRouter(
    prefix="/tools",
    tags=["tools"],
    responses={404: {"description": "Not found"}}
)


class Tool(Base):
    """
    Tool model for storing tool configurations and metadata.
    Each tool represents a specific data extraction capability
    that can be used by the Claude API.
    """
    __tablename__ = "tool"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Tool identification
    name = Column(String(100), nullable=False, unique=True)

    tool_type = Column(SQLEnum(ToolType, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    description = Column(Text, nullable=False)
    version = Column(String(20), nullable=False, default="1.0.0")

    # Tool configuration and capabilities
    capabilities = Column(JSON, nullable=False, default=dict)  # What the tool can do
    configuration = Column(JSON, nullable=False, default=dict)  # Tool-specific config

    # FIXED: Use native_enum=False for status as well
    status = Column(SQLEnum(ToolStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=ToolStatus.ACTIVE)
    is_active = Column(Boolean, default=True)

    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)

    # Relationships
    executions = relationship("ToolExecution", back_populates="tool", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tool '{self.name}' ({self.tool_type})>"


class ToolExecution(Base):
    """
    Model for tracking tool executions and their results.
    This helps in monitoring tool usage and performance.
    """
    __tablename__ = "tool_execution"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(50), nullable=False, unique=True)  # UUID for tracking
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Execution details
    tool_id = Column(Integer, ForeignKey('tool.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=True)

    # Execution data
    parameters = Column(JSON, nullable=False, default=dict)  # Input parameters
    result = Column(JSON, nullable=True)  # Execution result
    execution_metadata = Column(JSON, nullable=False, default=dict)  # Additional metadata

    # Performance tracking
    execution_time_ms = Column(Integer, nullable=True)  # Execution time in milliseconds
    status = Column(String(20), nullable=False, default="pending")  # pending, success, failed
    error_message = Column(Text, nullable=True)

    # Relationships
    tool = relationship("Tool", back_populates="executions")

    def __repr__(self):
        return f"<ToolExecution {self.execution_id} for tool {self.tool_id}>"

