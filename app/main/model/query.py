"""
Query processing and Claude API response schemas.
Contains all schemas related to query processing, tool selection,
and Claude API interactions.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Annotated

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .tool import Tool, ToolType


class QueryType(str, Enum):
    """Classification of query types"""
    ACTIVITY_INQUIRY = "activity_inquiry"
    SLEEP_ANALYSIS = "sleep_analysis"
    CARE_METRICS = "care_metrics"
    HEALTH_CHECK = "health_check"
    SCHEDULE_QUERY = "schedule_query"
    GENERAL_QUESTION = "general_question"
    COMPARATIVE_ANALYSIS = "comparative_analysis"


class ProcessingPhase(str, Enum):
    """Phases of query processing"""
    INITIALIZATION = "initialization"
    TOOL_SELECTION = "tool_selection"
    PARAMETER_EXTRACTION = "parameter_extraction"
    TOOL_EXECUTION = "tool_execution"
    RESULT_SYNTHESIS = "result_synthesis"
    COMPLETION = "completion"


class ExecutionStatus(str, Enum):
    """Status of individual operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class QueryRequest(BaseModel):
    """Schema for incoming query requests"""
    query: str = Field(..., description="User's natural language query")
    baby_id: Optional[int] = Field(None, description="Specific baby ID to filter data")
    include_thinking: bool = Field(False, description="Include Claude's thinking process")
    include_metadata: bool = Field(True, description="Include processing metadata")
    stream: bool = Field(False, description="Enable streaming response")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "How did my baby sleep last night?",
                    "baby_id": 123,
                    "include_thinking": True
                }
            ]
        }
    }


class ToolSelectionInfo(BaseModel):
    """Information about a selected tool"""
    tool_id: int
    tool_name: str
    tool_type: ToolType
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    selection_reason: str
    estimated_execution_time_ms: Optional[int] = None

    model_config = {"from_attributes": True}


class ToolExecutionInfo(BaseModel):
    """Information about tool execution"""
    tool_id: int
    tool_name: str
    tool_type: ToolType
    status: ExecutionStatus
    execution_time_ms: Optional[float] = None
    result_count: Optional[int] = None
    error_message: Optional[str] = None
    parameters_used: Annotated[ Dict[str, Any] , Field(default_factory=dict)]

    model_config = {"from_attributes": True}


# Dataclass models for internal processing
@dataclass
class ToolSelectionResult:
    """Result from Claude's tool selection process"""
    selected_tools: List[Tool]
    tool_info: List[ToolSelectionInfo]
    reasoning: str
    confidence: float
    query_classification: Optional[QueryType] = None
    thinking_process: Optional[str] = None
    fallback_used: bool = False
    selection_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "selected_tools": [
                {
                    "id": tool.id,
                    "name": tool.name,
                    "type": tool.tool_type,
                    "description": tool.description
                } for tool in self.selected_tools
            ],
            "tool_info": [info.__dict__ for info in self.tool_info],
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "query_classification": self.query_classification.value if self.query_classification else None,
            "thinking_process": self.thinking_process,
            "fallback_used": self.fallback_used,
            "selection_time_ms": self.selection_time_ms
        }


@dataclass
class QueryProcessingResult:
    """Complete result from query processing"""
    success: bool
    data: Dict[str, Any]
    tool_selection: ToolSelectionResult
    execution_summary: Dict[str, Any]
    processing_metadata: Dict[str, Any]
    error: Optional[str] = None
    total_processing_time_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "success": self.success,
            "data": self.data,
            "tool_selection": self.tool_selection.to_dict(),
            "execution_summary": self.execution_summary,
            "processing_metadata": self.processing_metadata,
            "error": self.error,
            "total_processing_time_ms": self.total_processing_time_ms
        }


# Response models for API endpoints
class QueryResponse(BaseModel):
    """Main response schema for query processing"""
    success: bool
    data: Dict[str, Any]
    metadata: Annotated[Dict[str, Any] , Field(default_factory=dict)]
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class ToolSelectionResponse(BaseModel):
    """Response schema for tool selection debugging"""
    query: str
    baby_id: Optional[int]
    available_tools: List[Dict[str, Any]]
    selected_tools: List[ToolSelectionInfo]
    reasoning: str
    confidence: float
    query_classification: Optional[QueryType]
    thinking_process: Optional[str] = None
    fallback_used: bool = False
    processing_time_ms: float

    model_config = {"from_attributes": True}


class StreamingEvent(BaseModel):
    """Schema for streaming events (SSE/WebSocket)"""
    event_type: str = Field(..., description="Type of event")
    phase: Optional[ProcessingPhase] = None
    message: str = Field(..., description="Human-readable message")
    data: Annotated[Optional[Dict[str, Any]] , Field(default_factory=dict)]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    progress_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "event_type": "phase_started",
                    "phase": "tool_selection",
                    "message": "Analyzing query and selecting appropriate tools...",
                    "progress_percentage": 25.0
                }
            ]
        }
    }


# Specialized response models for different query types
class ActivityAnalysisResponse(BaseModel):
    """Response for activity-related queries"""
    activities: List[Dict[str, Any]]
    summary: Dict[str, Any]
    trends: Optional[Dict[str, Any]] = None
    time_range: str
    total_activities: int

    model_config = {"from_attributes": True}


class SleepAnalysisResponse(BaseModel):
    """Response for sleep-related queries"""
    sleep_sessions: List[Dict[str, Any]]
    sleep_metrics: Dict[str, Any]
    patterns: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[str]] = None
    time_range: str

    model_config = {"from_attributes": True}


class CareMetricsResponse(BaseModel):
    """Response for care metrics queries"""
    caregivers: List[Dict[str, Any]]
    care_distribution: Dict[str, Any]
    participation_metrics: Dict[str, Any]
    time_range: str

    model_config = {"from_attributes": True}


# Error response models
class ProcessingError(BaseModel):
    """Detailed error information for query processing"""
    error_code: str
    error_message: str
    error_phase: Optional[ProcessingPhase] = None
    recovery_suggestions: Annotated[List[str] , Field(default_factory=list)]
    fallback_available: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class ValidationError(BaseModel):
    """Validation error details"""
    field_name: str
    error_message: str
    invalid_value: Any
    expected_format: Optional[str] = None

    model_config = {"from_attributes": True}


# Configuration models
class ClaudeAPIConfig(BaseModel):
    """Configuration for Claude API integration"""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 20000
    temperature: float = 1
    enable_thinking: bool = True
    thinking_budget_tokens: int = 19999
    max_tools_per_query: int = 3
    selection_confidence_threshold: float = 0.6

    model_config = {"from_attributes": True}


class QueryProcessingConfig(BaseModel):
    """Configuration for query processing"""
    enable_streaming: bool = True
    enable_websocket: bool = True
    cache_tool_selections: bool = False
    cache_ttl_seconds: int = 300
    max_concurrent_executions: int = 5
    execution_timeout_seconds: int = 30

    model_config = {"from_attributes": True}


# Utility models for complex operations
class BulkQueryRequest(BaseModel):
    """Schema for processing multiple queries"""
    queries: List[QueryRequest]
    batch_id: Optional[str] = None
    parallel_processing: bool = True
    max_concurrent: int = Field(3, ge=1, le=10)

    model_config = {"from_attributes": True}


class BulkQueryResponse(BaseModel):
    """Response for bulk query processing"""
    batch_id: str
    total_queries: int
    successful_queries: int
    failed_queries: int
    results: List[QueryResponse]
    processing_time_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class QueryAnalytics(BaseModel):
    """Analytics data for query processing"""
    total_queries_processed: int
    average_processing_time_ms: float
    most_used_tools: List[Dict[str, Any]]
    query_type_distribution: Dict[str, int]
    success_rate: float
    common_error_types: List[Dict[str, Any]]
    period_start: datetime
    period_end: datetime

    model_config = {"from_attributes": True}


router = APIRouter(
    prefix="/query",
    tags=["query"],
    responses={404: {"description": "Not found"}}
)


# Export commonly used types
__all__ = [
    # Enums
    "QueryType",
    "ProcessingPhase", 
    "ExecutionStatus",
    
    # Request/Response Models
    "QueryRequest",
    "QueryResponse",
    "ToolSelectionResponse",
    "StreamingEvent",
    
    # Result Classes (main ones)
    "ToolSelectionResult",
    "QueryProcessingResult",
    
    # Specialized Response Models
    "ActivityAnalysisResponse",
    "SleepAnalysisResponse", 
    "CareMetricsResponse",
    
    # Error Models
    "ProcessingError",
    "ValidationError",
    
    # Configuration Models
    "ClaudeAPIConfig",
    "QueryProcessingConfig",
    
    # Utility Models
    "BulkQueryRequest",
    "BulkQueryResponse",
    "QueryAnalytics",

    # Tools
    "ToolSelectionInfo",
    "ToolExecutionInfo",

    "router"
]
