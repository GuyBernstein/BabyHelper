from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.dashboard import (
    router,
    DashboardPreferenceUpdate,
    DashboardPreferenceResponse,
    TimeFrame
)
from app.main.model.user import User
from app.main.service.dashboard_service import (
    get_dashboard_data,
    get_or_create_dashboard_preferences,
    update_dashboard_preferences,
    get_recent_activities,
    get_upcoming_events,
    get_care_metrics
)
from app.main.service.oauth_service import get_current_user
from app.main.service.baby_service import get_all_babies_for_user, get_baby_if_authorized


@router.get("/dash", response_model=Dict[str, Any])
async def get_dashboard(
        baby_id: Optional[int] = Query(None, description="Filter data for a specific baby"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get dashboard data with all enabled widgets.

    Timeframe is determined by user preferences. To change the timeframe,
    update user preferences via PUT /dashboard/preferences endpoint.

    For custom timeframes, the date range is stored in user preferences.
    """
    # Fetch user preferences to get the default timeframe
    preferences = get_or_create_dashboard_preferences(db, current_user.id)
    timeframe = preferences.default_timeframe

    # If timeframe is CUSTOM, use the stored custom dates
    custom_start = None
    custom_end = None
    if timeframe == TimeFrame.CUSTOM:
        custom_start = preferences.custom_start_date
        custom_end = preferences.custom_end_date

        # Validate custom dates are set
        if not custom_start or not custom_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom timeframe selected but custom dates not set in preferences"
            )

    return get_dashboard_data(
        db,
        current_user.id,
        baby_id,
        timeframe,
        custom_start,
        custom_end
    )


@router.get("/preferences", response_model=DashboardPreferenceResponse)
async def get_dashboard_preferences(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get user's dashboard preferences including custom timeframe dates if set"""
    preferences = get_or_create_dashboard_preferences(db, current_user.id)

    # Convert to Pydantic model compatible dict
    preferences_dict = {
        "id": preferences.id,
        "created_at": preferences.created_at,
        "user_id": preferences.user_id,
        "layout_type": preferences.layout_type,
        "default_baby_id": preferences.default_baby_id,
        "default_timeframe": preferences.default_timeframe,
        "custom_start_date": preferences.custom_start_date,
        "custom_end_date": preferences.custom_end_date,
        "widgets_config": preferences.widgets_config or []  # Ensure this isn't None
    }

    return preferences_dict


@router.put("/preferences", response_model=DashboardPreferenceResponse)
async def update_dashboard_prefs(
        preferences: DashboardPreferenceUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update user's dashboard preferences with validation."""

    # Validate custom timeframe dates if timeframe is CUSTOM
    if preferences.default_timeframe == TimeFrame.CUSTOM:
        if not preferences.custom_start_date or not preferences.custom_end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="When setting timeframe to 'custom', both custom_start_date and custom_end_date must be provided"
            )

        if preferences.custom_start_date >= preferences.custom_end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="custom_start_date must be before custom_end_date"
            )

    # Validate widget configurations
    for widget in preferences.widgets_config:
        if 'type' not in widget:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each widget must have a 'type' field"
            )

        # Ensure widget has all required fields with defaults
        widget.setdefault('position', 0)
        widget.setdefault('enabled', True)
        widget.setdefault('timeframe', preferences.default_timeframe.value)

        # Validate widget-specific custom timeframe
        if widget.get('timeframe') == 'custom':
            custom_settings = widget.get('custom_settings', {})
            if not custom_settings.get('custom_start_date') or not custom_settings.get('custom_end_date'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Widget {widget['type']} has custom timeframe but missing custom dates"
                )

    updated_preferences = update_dashboard_preferences(db, current_user.id, preferences.model_dump())

    # Convert to Pydantic model compatible dict
    preferences_dict = {
        "id": updated_preferences.id,
        "created_at": updated_preferences.created_at,
        "user_id": updated_preferences.user_id,
        "layout_type": updated_preferences.layout_type,
        "default_baby_id": updated_preferences.default_baby_id,
        "default_timeframe": updated_preferences.default_timeframe,
        "custom_start_date": updated_preferences.custom_start_date,
        "custom_end_date": updated_preferences.custom_end_date,
        "widgets_config": updated_preferences.widgets_config or []
    }

    return preferences_dict


@router.get("/activities", response_model=List[Dict[str, Any]])
async def get_recent_activity_data(
        baby_id: Optional[int] = Query(None, description="Filter data for a specific baby"),
        limit: int = Query(10, description="Number of activities to return"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get recent activities for all babies or a specific baby.

    Timeframe is determined by the RECENT_ACTIVITIES widget configuration in user preferences.
    To change the timeframe, update the widget's timeframe in user preferences.
    """
    # Get user preferences to determine timeframe for activities widget
    preferences = get_or_create_dashboard_preferences(db, current_user.id)

    # Find the RECENT_ACTIVITIES widget configuration
    activities_widget = next(
        (w for w in preferences.widgets_config
         if w.get('type') == 'recent_activities'),
        None
    )

    # Use widget's timeframe or fall back to default preference
    timeframe = (activities_widget.get('timeframe')
                 if activities_widget
                 else preferences.default_timeframe)

    # Handle custom timeframe
    custom_start = None
    custom_end = None
    if timeframe == TimeFrame.CUSTOM:
        # Check if widget has its own custom dates
        if activities_widget and activities_widget.get('custom_settings'):
            custom_start = activities_widget['custom_settings'].get('custom_start_date')
            custom_end = activities_widget['custom_settings'].get('custom_end_date')

            # Convert string dates to datetime if needed
            if isinstance(custom_start, str):
                custom_start = datetime.fromisoformat(custom_start.replace('Z', '+00:00'))
            if isinstance(custom_end, str):
                custom_end = datetime.fromisoformat(custom_end.replace('Z', '+00:00'))

        # Fall back to preference-level custom dates
        if not custom_start or not custom_end:
            custom_start = preferences.custom_start_date
            custom_end = preferences.custom_end_date

        if not custom_start or not custom_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom timeframe selected but custom dates not configured"
            )

    # Get babies the user has access to
    all_babies = get_all_babies_for_user(db, current_user.id)
    baby_ids = [baby.id for baby in all_babies]

    # Filter to specific baby if requested
    if baby_id:
        baby = get_baby_if_authorized(db, baby_id, current_user.id)
        if isinstance(baby, dict):  # Error response
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this baby's data"
            )
        baby_ids = [baby_id]

    activities = get_recent_activities(
        db, baby_ids, timeframe, custom_start, custom_end, limit=limit
    )
    return activities


@router.get("/upcoming-events", response_model=List[Dict[str, Any]])
async def get_upcoming_event_data(
        baby_id: Optional[int] = Query(None, description="Filter data for a specific baby"),
        days_ahead: int = Query(7, description="Number of days to look ahead"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get upcoming events for all babies or a specific baby.

    Note: This endpoint uses days_ahead parameter instead of timeframe,
    as future events have a different time scope than historical data.
    """
    from app.main.service.baby_service import get_all_babies_for_user, get_baby_if_authorized

    # Get babies the user has access to
    all_babies = get_all_babies_for_user(db, current_user.id)
    baby_ids = [baby.id for baby in all_babies]

    # Filter to specific baby if requested
    if baby_id:
        baby = get_baby_if_authorized(db, baby_id, current_user.id)
        if isinstance(baby, dict):  # Error response
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this baby's data"
            )
        baby_ids = [baby_id]

    events = get_upcoming_events(
        db, baby_ids, days_ahead=days_ahead
    )
    return events


@router.get("/care-metrics", response_model=Dict[str, Any])
async def get_care_metrics_data(
        baby_id: Optional[int] = Query(None, description="Filter data for a specific baby"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Get care metrics for all babies or a specific baby.

    Timeframe is determined by the CARE_METRICS widget configuration in user preferences.
    To change the timeframe, update the widget's timeframe in user preferences.
    """
    from app.main.service.baby_service import get_all_babies_for_user, get_baby_if_authorized

    # Get user preferences to determine timeframe for care metrics widget
    preferences = get_or_create_dashboard_preferences(db, current_user.id)

    # Find the CARE_METRICS widget configuration
    metrics_widget = next(
        (w for w in preferences.widgets_config
         if w.get('type') == 'care_metrics'),
        None
    )

    # Use widget's timeframe or fall back to default preference
    timeframe = (metrics_widget.get('timeframe')
                 if metrics_widget
                 else preferences.default_timeframe)

    # Handle custom timeframe
    custom_start = None
    custom_end = None
    if timeframe == TimeFrame.CUSTOM:
        # Check if widget has its own custom dates
        if metrics_widget and metrics_widget.get('custom_settings'):
            custom_start = metrics_widget['custom_settings'].get('custom_start_date')
            custom_end = metrics_widget['custom_settings'].get('custom_end_date')

            # Convert string dates to datetime if needed
            if isinstance(custom_start, str):
                custom_start = datetime.fromisoformat(custom_start.replace('Z', '+00:00'))
            if isinstance(custom_end, str):
                custom_end = datetime.fromisoformat(custom_end.replace('Z', '+00:00'))

        # Fall back to preference-level custom dates
        if not custom_start or not custom_end:
            custom_start = preferences.custom_start_date
            custom_end = preferences.custom_end_date

        if not custom_start or not custom_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom timeframe selected but custom dates not configured"
            )

    # Get babies the user has access to
    all_babies = get_all_babies_for_user(db, current_user.id)
    baby_ids = [baby.id for baby in all_babies]

    # Filter to specific baby if requested
    if baby_id:
        baby = get_baby_if_authorized(db, baby_id, current_user.id)
        if isinstance(baby, dict):  # Error response
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this baby's data"
            )
        baby_ids = [baby_id]

    metrics = get_care_metrics(
        db, baby_ids, timeframe, custom_start, custom_end
    )
    return metrics
