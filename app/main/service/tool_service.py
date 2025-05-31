"""
Tool service for managing tools and their executions.
Handles tool CRUD operations and execution logic.
"""
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Type

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.main.model import Baby
from app.main.model.tool import Tool, ToolExecution, ToolType, ToolStatus
from app.main.service.baby_service import get_baby_if_authorized, get_all_babies_for_user
from app.main.service.dashboard_service import (
    get_recent_activities,
    get_upcoming_events,
    get_care_metrics
)
from app.main.service.sleep_service import get_sleep_patterns


def create_tool(db: Session, tool_data: Dict[str, Any]) -> Tool:
    """Create a new tool configuration"""
    # Check if tool with same name exists
    existing_tool = db.query(Tool).filter(Tool.name == tool_data['name']).first()
    if existing_tool:
        raise ValueError(f"Tool with name '{tool_data['name']}' already exists")

    # Convert string values to enum instances
    tool_type = ToolType(tool_data['tool_type'])
    status = ToolStatus(tool_data.get('status', ToolStatus.ACTIVE.value))

    new_tool = Tool(
        name=tool_data['name'],
        tool_type=tool_type,  # Now using enum instance
        description=tool_data['description'],
        version=tool_data.get('version', '1.0.0'),
        capabilities=tool_data.get('capabilities', {}),
        configuration=tool_data.get('configuration', {}),
        status=status  # Now using enum instance
    )

    db.add(new_tool)
    db.commit()
    db.refresh(new_tool)
    return new_tool


def get_tool(db: Session, tool_id: int) -> Optional[Tool]:
    """Get a tool by ID"""
    return db.query(Tool).filter(Tool.id == tool_id).first()


def get_tool_by_name(db: Session, name: str) -> Optional[Tool]:
    """Get a tool by name"""
    return db.query(Tool).filter(Tool.name == name).first()


def get_tools_by_type(db: Session, tool_type: ToolType) -> list[Type[Tool]]:
    """Get all tools of a specific type"""
    return db.query(Tool).filter(
        Tool.tool_type == tool_type,
        Tool.status == ToolStatus.ACTIVE
    ).all()


def get_active_tools(db: Session) -> list[Type[Tool]]:
    """Get all active tools"""
    return db.query(Tool).filter(
        Tool.status == ToolStatus.ACTIVE,  # Fixed: removed .value
        Tool.is_active == True
    ).all()


def update_tool(db: Session, tool_id: int, tool_data: Dict[str, Any]) -> Optional[Tool]:
    """Update a tool configuration"""
    tool = get_tool(db, tool_id)
    if not tool:
        return None

    # Update fields if provided
    if 'name' in tool_data:
        tool.name = tool_data['name']
    if 'description' in tool_data:
        tool.description = tool_data['description']
    if 'version' in tool_data:
        tool.version = tool_data['version']
    if 'capabilities' in tool_data:
        tool.capabilities = tool_data['capabilities']
    if 'configuration' in tool_data:
        tool.configuration = tool_data['configuration']
    if 'status' in tool_data:
        tool.status = ToolStatus(tool_data['status'])  # Convert to enum instance

    tool.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(tool)
    return tool


def execute_tool(
        db: Session,
        tool_id: int,
        user_id: int,
        parameters: Dict[str, Any],
        baby_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Execute a tool and return the results.
    This is the main entry point for tool execution.
    """

    start_time = time.time()
    execution_id = str(uuid.uuid4())

    # Get the tool
    tool = get_tool(db, tool_id)
    if not tool:
        raise ValueError(f"Tool with ID {tool_id} not found")

    if tool.status != ToolStatus.ACTIVE:
        raise ValueError(f"Tool '{tool.name}' is not active")

    # Create execution record
    execution = ToolExecution(
        execution_id=execution_id,
        tool_id=tool_id,
        user_id=user_id,
        baby_id=baby_id,
        parameters=parameters,
        status="running"
    )
    db.add(execution)
    db.commit()

    try:
        # Execute tool based on type
        result = _execute_tool_by_type(
            db, tool, user_id, baby_id, parameters
        )

        # Update execution record
        execution_time = int((time.time() - start_time) * 1000)
        execution.result = result
        execution.status = "success"
        execution.execution_time_ms = execution_time

        # Update tool usage stats
        tool.usage_count += 1
        tool.last_used_at = datetime.utcnow()

        db.commit()

        return {
            "tool_id": tool_id,
            "execution_id": execution_id,
            "status": "success",
            "data": result,
            "metadata": {
                "tool_name": tool.name,
                "tool_type": tool.tool_type,
                "execution_time_ms": execution_time
            },
            "execution_time_ms": execution_time
        }

    except Exception as e:
        # Update execution record with error
        execution.status = "failed"
        execution.error_message = str(e)
        execution.execution_time_ms = int((time.time() - start_time) * 1000)
        db.commit()

        raise


def _execute_tool_by_type(
        db: Session,
        tool: Tool,
        user_id: int,
        baby_id: Optional[int],
        parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute tool logic based on tool type.
    This is where the actual data extraction happens.
    """
    # Get baby IDs for data extraction
    if baby_id:
        # Verify user has access to this baby
        baby = get_baby_if_authorized(db, baby_id, user_id)
        if isinstance(baby, dict):  # Error response
            raise ValueError(baby.get('message', 'Unauthorized'))
        baby_ids = [baby_id]
    else:
        # Get all babies the user has access to
        babies = get_all_babies_for_user(db, user_id)
        baby_ids = [baby.id for baby in babies]

    # Execute based on tool type
    if tool.tool_type == ToolType.ACTIVITY_ANALYZER:
        return _execute_activity_analyzer(db, baby_ids, parameters)

    elif tool.tool_type == ToolType.SLEEP_PATTERN_ANALYZER:
        return _execute_sleep_analyzer(db, baby_ids, user_id, parameters)

    elif tool.tool_type == ToolType.CARE_METRICS_ANALYZER:
        return _execute_care_metrics_analyzer(db, baby_ids, parameters)

    elif tool.tool_type == ToolType.SCHEDULE_ASSISTANT:
        return _execute_schedule_assistant(db, baby_ids, parameters)

    # Add more tool types as needed
    else:
        raise ValueError(f"Tool type '{tool.tool_type}' not implemented")


def _execute_activity_analyzer(
        db: Session,
        baby_ids: List[int],
        parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze recent activities for the specified babies.
    Extracts and formats activity data from dashboard summaries.
    """
    # Extract parameters
    timeframe = parameters.get('timeframe', 'week')
    limit = parameters.get('limit', 20)
    activity_types = parameters.get('activity_types', None)

    # Get recent activities
    activities = get_recent_activities(
        db, baby_ids, timeframe, limit=limit
    )

    # Filter by activity types if specified
    if activity_types:
        activities = [a for a in activities if a['type'] in activity_types]

    # Format data for Claude API
    formatted_activities = []
    for activity in activities:
        formatted_activity = {
            "timestamp": activity['time'].isoformat(),
            "type": activity['type'],
            "baby_name": activity['baby_name'],
            "caregiver_name": activity['caregiver_name'],
            "details": activity['details']
        }
        formatted_activities.append(formatted_activity)

    # Generate summary statistics
    activity_counts = {}
    for activity in activities:
        activity_type = activity['type']
        if activity_type not in activity_counts:
            activity_counts[activity_type] = 0
        activity_counts[activity_type] += 1

    return {
        "summary": {
            "total_activities": len(activities),
            "timeframe": timeframe,
            "activity_counts": activity_counts,
            "babies_included": len(set(a['baby_id'] for a in activities))
        },
        "activities": formatted_activities
    }


def _execute_sleep_analyzer(
        db: Session,
        baby_ids: List[int],
        user_id: int,
        parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze sleep patterns for the specified babies.
    Provides insights into sleep quality and patterns.
    """
    # Extract and process parameters
    timeframe = parameters.get('timeframe', 7)

    if isinstance(timeframe, int):
        # Accept any positive integer with reasonable bounds
        if timeframe <= 0:
            days = 1  # Minimum of 1 day
        elif timeframe > 365:
            days = 365  # Maximum of 1 year for performance reasons
        else:
            days = timeframe
    else:
        days = 7  # Default fallback for any other type

    include_details = parameters.get('include_details', True)

    # Extract metrics parameter - default to all metrics if not specified
    requested_metrics = parameters.get('metrics', ['total_sleep', 'night_sleep', 'naps', 'quality'])
    if not isinstance(requested_metrics, list):
        requested_metrics = ['total_sleep', 'night_sleep', 'naps', 'quality']

    # Validate metrics
    valid_metrics = {'total_sleep', 'night_sleep', 'naps', 'quality'}
    requested_metrics = [m for m in requested_metrics if m in valid_metrics]

    # If no valid metrics specified, default to all
    if not requested_metrics:
        requested_metrics = list(valid_metrics)

    # Collect data from all babies
    all_patterns: Dict[int, Dict[str, Any]] = {}
    successful_babies: List[int] = []

    for baby_id in baby_ids:
        result = get_sleep_patterns(db, baby_id, user_id, days)
        if isinstance(result, dict) and result.get('status') == 'success':
            all_patterns[baby_id] = result['patterns']
            successful_babies.append(baby_id)

    # If no successful data, return empty result
    if not successful_babies:
        return _create_empty_result(days, requested_metrics)

    # Aggregate only requested metrics
    aggregated_data = _aggregate_metrics(all_patterns, successful_babies, requested_metrics)

    # Build summary based on requested metrics
    summary = {
        "analysis_period_days": days,
        "babies_analyzed": len(successful_babies),
        "metrics_analyzed": requested_metrics
    }

    # Add metric-specific results
    if 'total_sleep' in requested_metrics:
        summary["avg_total_sleep_hours"] = aggregated_data['avg_total_sleep_hours']

    if 'night_sleep' in requested_metrics:
        summary["avg_night_sleep_hours"] = aggregated_data['avg_night_sleep_hours']

    if 'naps' in requested_metrics:
        summary["avg_naps_per_day"] = aggregated_data['avg_naps_per_day']

    if 'quality' in requested_metrics:
        summary["avg_sleep_quality_score"] = aggregated_data['avg_sleep_quality_score']
        summary["sleep_quality_rating"] = aggregated_data['sleep_quality_rating']

    result = {"summary": summary}

    # Add detailed patterns if requested
    if include_details:
        detailed_patterns: Dict[int, Dict[str, Any]] = {}

        for baby_id in successful_babies:
            if baby_id in all_patterns:
                # Filter patterns based on requested metrics
                filtered_pattern = _filter_pattern_by_metrics(
                    all_patterns[baby_id],
                    requested_metrics
                )
                detailed_patterns[baby_id] = filtered_pattern

        result["detailed_patterns"] = detailed_patterns

    return result


def _create_empty_result(days: int, requested_metrics: List[str]) -> Dict[str, Any]:
    """Create an empty result with appropriate structure based on requested metrics."""
    summary = {
        "analysis_period_days": days,
        "babies_analyzed": 0,
        "metrics_analyzed": requested_metrics
    }

    # Add zeros for requested metrics
    if 'total_sleep' in requested_metrics:
        summary["avg_total_sleep_hours"] = 0

    if 'night_sleep' in requested_metrics:
        summary["avg_night_sleep_hours"] = 0

    if 'naps' in requested_metrics:
        summary["avg_naps_per_day"] = 0

    if 'quality' in requested_metrics:
        summary["avg_sleep_quality_score"] = 0
        summary["sleep_quality_rating"] = "No Data"

    return {"summary": summary}


def _aggregate_metrics(
        all_patterns: Dict[int, Dict[str, Any]],
        successful_babies: List[int],
        requested_metrics: List[str]
) -> Dict[str, Any]:
    """Aggregate only the requested metrics across all babies."""
    # Initialize aggregation variables only for requested metrics
    aggregated = {}
    baby_count = len(successful_babies)

    if 'total_sleep' in requested_metrics:
        aggregated['total_sleep_hours'] = 0.0

    if 'night_sleep' in requested_metrics:
        aggregated['total_night_sleep_hours'] = 0.0

    if 'naps' in requested_metrics:
        aggregated['total_naps'] = 0.0

    if 'quality' in requested_metrics:
        aggregated['total_quality_scores'] = 0.0
        aggregated['babies_with_valid_scores'] = 0

    # Collect data for requested metrics only
    for baby_id in successful_babies:
        patterns = all_patterns.get(baby_id, {})
        if patterns and 'summary' in patterns:
            summary = patterns['summary']

            if 'total_sleep' in requested_metrics:
                aggregated['total_sleep_hours'] += float(summary.get('avg_total_sleep_hours', 0))

            if 'night_sleep' in requested_metrics:
                aggregated['total_night_sleep_hours'] += float(summary.get('avg_night_sleep_hours', 0))

            if 'naps' in requested_metrics:
                aggregated['total_naps'] += float(summary.get('avg_naps_per_day', 0))

            if 'quality' in requested_metrics:
                quality_score = summary.get('sleep_quality_score', 0)
                if quality_score > 0:  # Valid score (not "No Data")
                    aggregated['total_quality_scores'] += float(quality_score)
                    aggregated['babies_with_valid_scores'] += 1

    # Calculate averages
    result = {}

    if 'total_sleep' in requested_metrics:
        result['avg_total_sleep_hours'] = round(aggregated['total_sleep_hours'] / baby_count, 1)

    if 'night_sleep' in requested_metrics:
        result['avg_night_sleep_hours'] = round(aggregated['total_night_sleep_hours'] / baby_count, 1)

    if 'naps' in requested_metrics:
        result['avg_naps_per_day'] = round(aggregated['total_naps'] / baby_count, 1)

    if 'quality' in requested_metrics:
        if aggregated['babies_with_valid_scores'] > 0:
            avg_quality_score = aggregated['total_quality_scores'] / aggregated['babies_with_valid_scores']
            result['avg_sleep_quality_score'] = round(avg_quality_score)

            # Determine overall quality rating
            if avg_quality_score >= 80:
                result['sleep_quality_rating'] = "Excellent"
            elif avg_quality_score >= 65:
                result['sleep_quality_rating'] = "Good"
            elif avg_quality_score >= 45:
                result['sleep_quality_rating'] = "Fair"
            else:
                result['sleep_quality_rating'] = "Poor"
        else:
            result['avg_sleep_quality_score'] = 0
            result['sleep_quality_rating'] = "No Data"

    return result


def _filter_pattern_by_metrics(
        pattern: Dict[str, Any],
        requested_metrics: List[str]
) -> Dict[str, Any]:
    """Filter pattern data to include only requested metrics."""
    filtered = {}

    if 'summary' in pattern:
        filtered_summary = {}
        summary = pattern['summary']

        # Always include these meta fields
        filtered_summary['total_days_analyzed'] = summary.get('total_days_analyzed')
        filtered_summary['days_with_sleep_data'] = summary.get('days_with_sleep_data')

        # Add metric-specific fields
        if 'total_sleep' in requested_metrics:
            filtered_summary['avg_total_sleep_minutes'] = summary.get('avg_total_sleep_minutes')
            filtered_summary['avg_total_sleep_hours'] = summary.get('avg_total_sleep_hours')

        if 'night_sleep' in requested_metrics:
            filtered_summary['avg_night_sleep_hours'] = summary.get('avg_night_sleep_hours')

        if 'naps' in requested_metrics:
            filtered_summary['avg_naps_per_day'] = summary.get('avg_naps_per_day')

        if 'quality' in requested_metrics:
            filtered_summary['sleep_quality_score'] = summary.get('sleep_quality_score')
            filtered_summary['sleep_quality_rating'] = summary.get('sleep_quality_rating')

        filtered['summary'] = filtered_summary

    # Include additional details based on metrics
    if 'total_sleep' in requested_metrics and 'daily_sleep' in pattern:
        filtered['daily_sleep'] = pattern['daily_sleep']

    if ('total_sleep' in requested_metrics or 'quality' in requested_metrics) and 'by_location' in pattern:
        filtered['by_location'] = pattern['by_location']

    return filtered


def _execute_care_metrics_analyzer(
        db: Session,
        baby_ids: List[int],
        parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze care metrics to understand caregiver participation.
    Useful for understanding care sharing patterns.
    """
    # Extract parameters
    timeframe = parameters.get('timeframe', 'month')

    # Get care metrics
    metrics = get_care_metrics(db, baby_ids, timeframe)

    # Format for Claude API
    formatted_metrics = {
        "summary": {
            "timeframe": timeframe,
            "total_activities": metrics['total_activities'],
            "babies_included": len(baby_ids)
        },
        "caregiver_participation": {},
        "activity_distribution": metrics['by_activity_type']
    }

    # Format caregiver data
    for caregiver_id, data in metrics['by_caregiver'].items():
        caregiver_info = data['caregiver']
        formatted_metrics["caregiver_participation"][caregiver_id] = {
            "name": caregiver_info['name'],
            "is_primary": caregiver_info['is_primary'],
            "total_activities": data['total'],
            "percentage": data['percentage'],
            "activities_by_type": data['by_activity_type']
        }

    return formatted_metrics


def _execute_schedule_assistant(
        db: Session,
        baby_ids: List[int],
        parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Get upcoming events and suggest schedule optimizations.
    Helps with planning and scheduling care activities.
    """
    # Extract parameters
    days_ahead = parameters.get('days_ahead', 7)
    include_suggestions = parameters.get('include_suggestions', True)

    # Get upcoming events
    events = get_upcoming_events(db, baby_ids, days_ahead)

    # Format events
    formatted_events = []
    for event in events:
        formatted_event = {
            "timestamp": event['time'].isoformat(),
            "type": event['type'],
            "baby_name": event['baby_name'],
            "details": event['details']
        }
        formatted_events.append(formatted_event)

    result = {
        "summary": {
            "days_ahead": days_ahead,
            "total_events": len(events),
            "babies_included": len(baby_ids)
        },
        "events": formatted_events
    }

    # Add scheduling suggestions if requested
    if include_suggestions:
        suggestions = _generate_schedule_suggestions(events)
        result["suggestions"] = suggestions

    return result


def _generate_schedule_suggestions(events: List[Dict[str, Any]]) -> List[str]:
    """
    Generate basic scheduling suggestions based on events.
    This is a placeholder for more sophisticated logic.
    """
    suggestions = []

    # Count events by type
    event_counts = {}
    for event in events:
        event_type = event['type']
        if event_type not in event_counts:
            event_counts[event_type] = 0
        event_counts[event_type] += 1

    # Generate suggestions based on patterns
    if event_counts.get('doctor_visit', 0) > 2:
        suggestions.append("Multiple doctor visits scheduled. Consider consolidating if possible.")

    if event_counts.get('medication', 0) > 0:
        suggestions.append("Medication reminders set. Ensure supplies are stocked.")

    return suggestions