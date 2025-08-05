from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.main.model import Growth, Pumping
from app.main.model.baby import Baby
from app.main.model.dashboard import DashboardPreference, WidgetType, TimeFrame, ChecklistItemStatus, ChecklistItemType
from app.main.model.diaper import Diaper
from app.main.model.doctor_visit import DoctorVisit
from app.main.model.feeding import Feeding
from app.main.model.health import Health
from app.main.model.medication import Medication
from app.main.model.milestone import Milestone
from app.main.model.photo import Photo
from app.main.model.sleep import Sleep
from app.main.model.user import User
from app.main.service.baby_service import get_all_babies_for_user
from app.main.service.sleep_service import get_sleep_patterns as get_sleep_analysis


def get_or_create_dashboard_preferences(db: Session, user_id: int) -> DashboardPreference:
    """
    Get existing dashboard preferences or create default ones for a user.

    Args:
        db: Database session
        user_id: ID of the user

    Returns:
        DashboardPreference object with user's preferences
    """
    preferences = db.query(DashboardPreference).filter(
        DashboardPreference.user_id == user_id
    ).first()

    if preferences:
        # Ensure widgets_config is not None
        if preferences.widgets_config is None:
            preferences.widgets_config = _get_default_widgets_config()
            db.commit()
        return preferences

    # Create default preferences
    new_preferences = DashboardPreference(
        user_id=user_id,
        layout_type="grid",
        default_timeframe=TimeFrame.WEEK,
        widgets_config=_get_default_widgets_config()
    )

    db.add(new_preferences)
    db.commit()
    db.refresh(new_preferences)
    return new_preferences


def update_dashboard_preferences(db: Session, user_id: int, preferences_data: Dict[str, Any]) -> DashboardPreference:
    """
    Update dashboard preferences for a user.

    Args:
        db: Database session
        user_id: ID of the user
        preferences_data: Dictionary containing preference updates

    Returns:
        Updated DashboardPreference object
    """
    preferences = get_or_create_dashboard_preferences(db, user_id)

    # Update basic preferences
    preferences.layout_type = preferences_data.get('layout_type', preferences.layout_type)
    preferences.default_baby_id = preferences_data.get('default_baby_id', preferences.default_baby_id)
    preferences.default_timeframe = preferences_data.get('default_timeframe', preferences.default_timeframe)

    # Update custom timeframe dates if provided
    if 'custom_start_date' in preferences_data:
        preferences.custom_start_date = preferences_data['custom_start_date']
    if 'custom_end_date' in preferences_data:
        preferences.custom_end_date = preferences_data['custom_end_date']

    # Update widgets configuration
    widgets_key = 'widgets_config' if 'widgets_config' in preferences_data else 'widgets'
    if widgets_key in preferences_data:
        preferences.widgets_config = [
            _normalize_widget_config(widget)
            for widget in preferences_data[widgets_key]
        ]

    db.commit()
    db.refresh(preferences)
    return preferences


def get_dashboard_data(
        db: Session,
        user_id: int,
        baby_id: Optional[int] = None,
        timeframe: Optional[str] = None,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get all dashboard data based on user preferences.

    Args:
        db: Database session
        user_id: ID of the user
        baby_id: Optional specific baby ID to filter data
        timeframe: Optional timeframe override
        custom_start: Optional custom start date
        custom_end: Optional custom end date

    Returns:
        Dictionary containing dashboard data with babies, preferences, and widgets
    """
    # Get user preferences
    preferences = get_or_create_dashboard_preferences(db, user_id)

    # Determine timeframe and baby scope
    timeframe = timeframe or preferences.default_timeframe
    baby_id = baby_id or preferences.default_baby_id

    # Get accessible babies
    babies = get_all_babies_for_user(db, user_id)
    baby_ids = _get_baby_ids_for_dashboard(babies, baby_id)

    # Build dashboard response
    dashboard_data = {
        'babies': _serialize_babies(babies),
        'preferences': _serialize_preferences(preferences),
        'widgets': _get_widget_data(db, preferences, baby_ids, timeframe, custom_start, custom_end)
    }

    return dashboard_data


def get_recent_activities(
        db: Session,
        baby_ids: List[int],
        timeframe: str,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None,
        limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get recent activities across all tracking categories for specified babies.

    Args:
        db: Database session
        baby_ids: List of baby IDs to get activities for
        timeframe: Time period to query
        custom_start: Optional custom start date
        custom_end: Optional custom end date
        limit: Maximum number of activities to return

    Returns:
        List of activity dictionaries sorted by time (newest first)
    """
    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)
    activities = []

    # Activity type configurations
    activity_configs = [
        (Feeding, 'feeding', 'start_time', _format_feeding_details),
        (Sleep, 'sleep', 'start_time', _format_sleep_details),
        (Diaper, 'diaper', 'time', _format_diaper_details),
        (Health, 'health', 'time', _format_health_details),
    ]

    # Collect activities from each type
    for model, activity_type, time_field, formatter in activity_configs:
        query = db.query(model).filter(
            model.baby_id.in_(baby_ids),
            getattr(model, time_field).between(start_date, end_date)
        ).order_by(desc(getattr(model, time_field))).limit(limit)

        for record in query.all():
            activity = _create_activity_entry(
                db, record, activity_type,
                getattr(record, time_field),
                formatter
            )
            activities.append(activity)

    # Sort all activities by time and return top limit
    activities.sort(key=lambda x: x['time'], reverse=True)
    return activities[:limit]


def get_baby_care_checklist(
        db: Session, baby_ids: List[int]
) -> List[Dict[str, Any]]:
    """
    Generate a baby care checklist to help parents troubleshoot why their baby might be crying.
    Include tracking data for gas relief, comfort, and environmental items.

    Args:
        db: Database session
        baby_ids: List of baby IDs to generate checklist for

    Returns:
        List of checklist items formatted as "events"
    """
    checklist_items = []

    # Generate checklist for each baby
    for baby_id in baby_ids:
        baby = db.query(Baby).filter(Baby.id == baby_id).first()
        if not baby:
            continue

        baby_name = baby.fullname

        # 1. Feeding Check
        last_feeding = db.query(Feeding).filter(
            Feeding.baby_id == baby_id
        ).order_by(desc(Feeding.start_time)).first()

        feeding_item = _create_checklist_item(
            baby_id=baby_id,
            baby_name=baby_name,
            item_type=ChecklistItemType.FEEDING,
            title="When did the baby last eat?",
            description="Babies typically need feeding every 2-4 hours.",
            last_activity=last_feeding.start_time if last_feeding else None,
            threshold_hours=3,  # Suggest checking if more than 3 hours
            db=db  # Pass db for tracking data
        )
        checklist_items.append(feeding_item)

        # 2. Diaper Check
        last_diaper = db.query(Diaper).filter(
            Diaper.baby_id == baby_id
        ).order_by(desc(Diaper.time)).first()

        diaper_item = _create_checklist_item(
            baby_id=baby_id,
            baby_name=baby_name,
            item_type=ChecklistItemType.DIAPER,
            title="Check if the diaper is wet or soiled",
            description="A wet or dirty diaper can cause significant discomfort.",
            last_activity=last_diaper.time if last_diaper else None,
            threshold_hours=2,  # Suggest checking if more than 2 hours
            db=db
        )
        checklist_items.append(diaper_item)

        # 3. Sleep Check
        last_sleep = db.query(Sleep).filter(
            Sleep.baby_id == baby_id
        ).order_by(desc(Sleep.start_time)).first()

        # Calculate when baby last woke up if sleep has ended
        last_awake_time = None
        if last_sleep and last_sleep.end_time:
            last_awake_time = last_sleep.end_time

        sleep_item = _create_checklist_item(
            baby_id=baby_id,
            baby_name=baby_name,
            item_type=ChecklistItemType.SLEEP,
            title="When did the baby last sleep?",
            description="Overtired babies often cry more. Most babies need sleep every 1-3 hours.",
            last_activity=last_awake_time,
            threshold_hours=2,  # Suggest sleep if awake more than 2 hours
            db=db
        )
        checklist_items.append(sleep_item)

        # 4. Gas Relief Check - Now includes tracking data
        gas_item = _create_checklist_item(
            baby_id=baby_id,
            baby_name=baby_name,
            item_type=ChecklistItemType.GAS_RELIEF,
            title="Consider if the baby needs to burp",
            description="Gas can cause significant discomfort.",
            last_activity=None,  # Will be overridden by tracking data if available
            threshold_hours=0.5,  # Suggest burping within 30 minutes of feeding
            db=db
        )
        checklist_items.append(gas_item)

        # 5. Comfort Check - Now includes tracking data
        comfort_item = _create_checklist_item(
            baby_id=baby_id,
            baby_name=baby_name,
            item_type=ChecklistItemType.COMFORT,
            title="Does the baby need physical touch or holding?",
            description="Babies need comfort and security.",
            last_activity=None,  # Will be overridden by tracking data if available
            threshold_hours=2,  # Suggest comfort check every 2 hours
            db=db
        )
        checklist_items.append(comfort_item)

        # 6. Environmental Check - Now includes tracking data
        environment_item = _create_checklist_item(
            baby_id=baby_id,
            baby_name=baby_name,
            item_type=ChecklistItemType.ENVIRONMENT,
            title="Check for overstimulation (noise, lights, people, colors)",
            description="Too much sensory input can overwhelm babies.",
            last_activity=None,  # Will be overridden by tracking data if available
            threshold_hours=6,  # Environmental checks less frequent
            db=db
        )
        checklist_items.append(environment_item)

    # Sort checklist items by priority (highest first)
    checklist_items.sort(key=lambda x: x['details']['priority'], reverse=True)

    return checklist_items


def create_checklist_tracking(
        db: Session,
        user_id: int,
        tracking_data: Dict[str, Any]
) -> Any:
    """
    Create a tracking record for gas relief, comfort, or environmental factors.

    Args:
        db: Database session
        user_id: ID of the user creating the tracking
        tracking_data: Dictionary containing tracking information

    Returns:
        Created tracking record
    """
    from app.main.model.dashboard import (
        GasReliefTracking, ComfortTracking, EnvironmentalTracking,
        ChecklistItemType
    )

    item_type = tracking_data['item_type']
    baby_id = tracking_data['baby_id']
    notes = tracking_data.get('notes')

    if item_type == ChecklistItemType.GAS_RELIEF:
        # Create gas relief tracking
        tracking = GasReliefTracking(
            baby_id=baby_id,
            recorded_by=user_id,
            status=tracking_data.get('status', 'no_action'),
            effective=None,  # Will be updated based on future crying episodes
            notes=notes
        )

    elif item_type == ChecklistItemType.COMFORT:
        # Create comfort tracking
        tracking = ComfortTracking(
            baby_id=baby_id,
            recorded_by=user_id,
            comfort_type=tracking_data.get('status', 'holding'),
            duration_minutes=tracking_data.get('duration_minutes'),
            effective=None,  # Will be updated based on future crying episodes
            notes=notes
        )

    elif item_type == ChecklistItemType.ENVIRONMENT:
        # Create environmental tracking
        factors_adjusted = tracking_data.get('factors_adjusted', [])
        if not factors_adjusted and tracking_data.get('status'):
            factors_adjusted = [tracking_data['status']]

        tracking = EnvironmentalTracking(
            baby_id=baby_id,
            recorded_by=user_id,
            factors_checked=factors_adjusted,  # What was checked
            factors_adjusted=factors_adjusted,  # What was adjusted
            notes=notes
        )
    else:
        raise ValueError(f"Invalid item type: {item_type}")

    db.add(tracking)
    db.commit()
    db.refresh(tracking)

    return tracking


def get_checklist_history(
        db: Session,
        baby_id: int,
        item_type: ChecklistItemType,
        limit: int = 10
) -> Dict[str, Any]:
    """
    Get tracking history for a specific checklist item.

    Args:
        db: Database session
        baby_id: ID of the baby
        item_type: Type of checklist item
        limit: Maximum number of records to return

    Returns:
        Dictionary containing current status, last tracking, and recent history
    """
    from app.main.model.dashboard import (
        GasReliefTracking, ComfortTracking, EnvironmentalTracking,
        ChecklistItemStatus
    )

    # Determine which model to query based on item type
    if item_type == ChecklistItemType.GAS_RELIEF:
        model = GasReliefTracking
        status_field = 'status'
    elif item_type == ChecklistItemType.COMFORT:
        model = ComfortTracking
        status_field = 'comfort_type'
    elif item_type == ChecklistItemType.ENVIRONMENT:
        model = EnvironmentalTracking
        status_field = 'factors_adjusted'
    else:
        raise ValueError(f"Invalid item type: {item_type}")

    # Get recent tracking records
    records = db.query(model).filter(
        model.baby_id == baby_id
    ).order_by(desc(model.created_at)).limit(limit).all()

    # Get the most recent record
    last_tracking = None
    if records:
        last_record = records[0]
        last_tracking = _format_tracking_record(last_record, item_type)

    # Format all records for history
    recent_history = [_format_tracking_record(record, item_type) for record in records]

    # Determine current status based on last tracking time
    current_status = _determine_current_checklist_status(last_tracking, item_type)

    return {
        'current_status': current_status,
        'last_tracking': last_tracking,
        'recent_history': recent_history
    }


def get_checklist_insights(
        db: Session,
        baby_id: int,
        item_type: ChecklistItemType
) -> Dict[str, Any]:
    """
    Generate insights based on tracking history for a checklist item.

    Args:
        db: Database session
        baby_id: ID of the baby
        item_type: Type of checklist item

    Returns:
        Dictionary containing insights and patterns
    """
    from app.main.model.dashboard import (
        GasReliefTracking, ComfortTracking, EnvironmentalTracking
    )
    from sqlalchemy import func

    insights = {
        'most_common_actions': [],
        'effectiveness_patterns': {},
        'time_patterns': {},
        'recommendations': []
    }

    if item_type == ChecklistItemType.GAS_RELIEF:
        # Analyze gas relief patterns
        # Get most common actions
        common_actions = db.query(
            GasReliefTracking.status,
            func.count(GasReliefTracking.id).label('count')
        ).filter(
            GasReliefTracking.baby_id == baby_id
        ).group_by(GasReliefTracking.status).order_by(desc('count')).limit(3).all()

        insights['most_common_actions'] = [
            {'action': action, 'count': count} for action, count in common_actions
        ]

        # Get effectiveness data (where marked)
        effective_actions = db.query(GasReliefTracking).filter(
            GasReliefTracking.baby_id == baby_id,
            GasReliefTracking.effective == True
        ).all()

        if effective_actions:
            insights['effectiveness_patterns'] = {
                'most_effective': _get_most_effective_action(effective_actions, 'status'),
                'success_rate': f"{len(effective_actions) / len(common_actions) * 100:.0f}%" if common_actions else "0%"
            }

        # Recommendations based on patterns
        if common_actions:
            most_used = common_actions[0][0]
            insights['recommendations'].append(
                f"You most frequently use {most_used}. Consider trying different techniques if this isn't effective."
            )

    elif item_type == ChecklistItemType.COMFORT:
        # Analyze comfort patterns
        # Get most common comfort methods
        common_methods = db.query(
            ComfortTracking.comfort_type,
            func.count(ComfortTracking.id).label('count'),
            func.avg(ComfortTracking.duration_minutes).label('avg_duration')
        ).filter(
            ComfortTracking.baby_id == baby_id
        ).group_by(ComfortTracking.comfort_type).order_by(desc('count')).limit(3).all()

        insights['most_common_actions'] = [
            {
                'method': method,
                'count': count,
                'avg_duration': f"{avg_duration:.0f} min" if avg_duration else "N/A"
            }
            for method, count, avg_duration in common_methods
        ]

        # Time analysis - when comfort is most needed
        comfort_by_hour = db.query(
            func.extract('hour', ComfortTracking.created_at).label('hour'),
            func.count(ComfortTracking.id).label('count')
        ).filter(
            ComfortTracking.baby_id == baby_id
        ).group_by('hour').order_by(desc('count')).limit(3).all()

        if comfort_by_hour:
            insights['time_patterns'] = {
                'peak_hours': [f"{hour}:00" for hour, _ in comfort_by_hour],
                'description': "Times when baby most often needs comfort"
            }

        # Recommendations
        if common_methods:
            insights['recommendations'].append(
                "Vary comfort techniques to prevent dependency on a single method."
            )
            if any(duration and duration > 30 for _, _, duration in common_methods):
                insights['recommendations'].append(
                    "Consider shorter comfort sessions to encourage self-soothing."
                )

    elif item_type == ChecklistItemType.ENVIRONMENT:
        # Analyze environmental patterns
        # Get all environmental checks
        env_records = db.query(EnvironmentalTracking).filter(
            EnvironmentalTracking.baby_id == baby_id
        ).all()

        if env_records:
            # Count frequency of each factor
            factor_counts = defaultdict(int)
            for record in env_records:
                for factor in record.factors_adjusted:
                    factor_counts[factor] += 1

            # Sort by frequency
            sorted_factors = sorted(factor_counts.items(), key=lambda x: x[1], reverse=True)[:3]

            insights['most_common_actions'] = [
                {'factor': factor, 'count': count}
                for factor, count in sorted_factors
            ]

            # Time patterns - when environmental issues occur
            env_by_hour = db.query(
                func.extract('hour', EnvironmentalTracking.created_at).label('hour'),
                func.count(EnvironmentalTracking.id).label('count')
            ).filter(
                EnvironmentalTracking.baby_id == baby_id
            ).group_by('hour').order_by(desc('count')).limit(3).all()

            if env_by_hour:
                insights['time_patterns'] = {
                    'peak_hours': [f"{hour}:00" for hour, _ in env_by_hour],
                    'description': "Times when environmental adjustments are most needed"
                }

            # Recommendations based on patterns
            if sorted_factors:
                most_common = sorted_factors[0][0]
                if 'too_bright' in [f[0] for f in sorted_factors]:
                    insights['recommendations'].append(
                        "Light sensitivity is common. Consider blackout curtains or dimmer switches."
                    )
                if 'too_loud' in [f[0] for f in sorted_factors]:
                    insights['recommendations'].append(
                        "Noise sensitivity detected. White noise machines can help mask sudden sounds."
                    )
                if any('too_hot' in f[0] or 'too_cold' in f[0] for f in sorted_factors):
                    insights['recommendations'].append(
                        "Temperature regulation is important. Keep room between 68-72°F (20-22°C)."
                    )

    return insights


def _format_tracking_record(record: Any, item_type: ChecklistItemType) -> Dict[str, Any]:
    """Format a tracking record for API response."""
    base_data = {
        'id': record.id,
        'created_at': record.created_at,
        'baby_id': record.baby_id,
        'item_type': item_type.value,
        'recorded_by': record.recorded_by,
        'notes': record.notes if hasattr(record, 'notes') else None
    }

    if item_type == ChecklistItemType.GAS_RELIEF:
        base_data['status'] = record.status
        base_data['effective'] = record.effective

    elif item_type == ChecklistItemType.COMFORT:
        base_data['status'] = record.comfort_type
        base_data['duration_minutes'] = record.duration_minutes
        base_data['effective'] = record.effective

    elif item_type == ChecklistItemType.ENVIRONMENT:
        base_data['factors_adjusted'] = record.factors_adjusted
        base_data['factors_checked'] = record.factors_checked
        base_data['room_temp'] = record.room_temp if hasattr(record, 'room_temp') else None
        base_data['noise_level'] = record.noise_level if hasattr(record, 'noise_level') else None
        base_data['light_level'] = record.light_level if hasattr(record, 'light_level') else None

    return base_data


def _determine_current_checklist_status(
        last_tracking: Optional[Dict[str, Any]],
        item_type: ChecklistItemType
) -> ChecklistItemStatus:
    """Determine current status based on last tracking time."""
    if not last_tracking:
        return ChecklistItemStatus.NOT_TRACKED

    # Calculate time since last tracking
    now = datetime.utcnow()
    last_time = last_tracking['created_at']
    hours_since = (now - last_time).total_seconds() / 3600

    # Status thresholds vary by item type
    if item_type == ChecklistItemType.GAS_RELIEF:
        # Gas relief is typically needed after feeding
        if hours_since < 1:
            return ChecklistItemStatus.OK
        elif hours_since < 3:
            return ChecklistItemStatus.CHECK_NEEDED
        else:
            return ChecklistItemStatus.ACTION_REQUIRED

    elif item_type == ChecklistItemType.COMFORT:
        # Comfort needs are more variable
        if hours_since < 2:
            return ChecklistItemStatus.OK
        elif hours_since < 4:
            return ChecklistItemStatus.CHECK_NEEDED
        else:
            return ChecklistItemStatus.ACTION_REQUIRED

    elif item_type == ChecklistItemType.ENVIRONMENT:
        # Environmental factors are less time-sensitive
        if hours_since < 6:
            return ChecklistItemStatus.OK
        elif hours_since < 12:
            return ChecklistItemStatus.CHECK_NEEDED
        else:
            return ChecklistItemStatus.ACTION_REQUIRED

    return ChecklistItemStatus.CHECK_NEEDED


def _get_most_effective_action(records: List[Any], field_name: str) -> str:
    """Find the most effective action from tracking records."""
    action_counts = defaultdict(int)
    for record in records:
        action = getattr(record, field_name)
        if action:
            action_counts[action] += 1

    if action_counts:
        return max(action_counts, key=action_counts.get)
    return "Unknown"


def _create_checklist_item(
        baby_id: int,
        baby_name: str,
        item_type: ChecklistItemType,
        title: str,
        description: str,
        last_activity: Optional[datetime],
        threshold_hours: float,
        db: Session = None  # Add db parameter
) -> Dict[str, Any]:
    """
    Create a checklist item formatted as an event for frontend compatibility.
    Enhanced to include tracking data for gas relief, comfort, and environment items.
    """
    now = datetime.utcnow()

    # For tracked items, get the last tracking data
    last_tracking_data = None
    if db and item_type in [ChecklistItemType.GAS_RELIEF, ChecklistItemType.COMFORT, ChecklistItemType.ENVIRONMENT]:
        history = get_checklist_history(db, baby_id, item_type, limit=1)
        if history['last_tracking']:
            last_tracking_data = history['last_tracking']
            # Override last_activity with tracking time
            last_activity = last_tracking_data['created_at']

    # Calculate time since last activity and status
    if last_activity:
        time_diff = now - last_activity
        hours_since = time_diff.total_seconds() / 3600

        # Determine status based on threshold
        if hours_since > threshold_hours:
            status = ChecklistItemStatus.ACTION_REQUIRED
            priority = 2  # High priority
        elif hours_since > threshold_hours * 0.75:
            status = ChecklistItemStatus.CHECK_NEEDED
            priority = 1  # Medium priority
        else:
            status = ChecklistItemStatus.OK
            priority = 0  # Low priority

        # Format time since last activity
        if hours_since < 1:
            time_since = f"{int(hours_since * 60)} minutes ago"
        elif hours_since < 24:
            time_since = f"{round(hours_since, 1)} hours ago"
        else:
            time_since = f"{round(hours_since / 24, 1)} days ago"

    else:
        # No tracking data available
        status = ChecklistItemStatus.NOT_TRACKED
        priority = 1  # Medium priority for untracked items
        time_since = "No recent data"
        hours_since = float('inf')

    # Determine action suggestion based on item type and status
    action_suggested = _get_action_suggestion(item_type, status, hours_since)

    # Add tracking-specific information to action suggestion
    if last_tracking_data:
        if item_type == ChecklistItemType.GAS_RELIEF:
            action_suggested += f" (Last action: {last_tracking_data.get('status', 'Unknown')})"
        elif item_type == ChecklistItemType.COMFORT:
            action_suggested += f" (Last method: {last_tracking_data.get('status', 'Unknown')})"
        elif item_type == ChecklistItemType.ENVIRONMENT:
            factors = last_tracking_data.get('factors_adjusted', [])
            if factors:
                action_suggested += f" (Last adjusted: {', '.join(factors)})"

    # Create the checklist item in event format for compatibility
    return {
        'id': f"checklist_{item_type.value}_{baby_id}",
        'type': 'checklist_item',
        'time': last_activity or now,  # Use current time if no last activity
        'baby_id': baby_id,
        'baby_name': baby_name,
        'details': {
            'item_type': item_type.value,
            'status': status.value,
            'title': title,
            'description': description,
            'last_activity_time': last_activity,
            'time_since_last': time_since,
            'action_suggested': action_suggested,
            'priority': priority,
            'last_tracking_data': last_tracking_data  # Include tracking data for frontend
        }
    }


def _get_action_suggestion(item_type: ChecklistItemType, status: ChecklistItemStatus, hours_since: float) -> str:
    """
    Get specific action suggestion based on checklist item type and status.

    Args:
        item_type: Type of checklist item
        status: Current status of the item
        hours_since: Hours since last relevant activity

    Returns:
        Action suggestion string
    """
    if status == ChecklistItemStatus.NOT_TRACKED:
        return "Start tracking this activity to get personalized suggestions"

    suggestions = {
        ChecklistItemType.FEEDING: {
            ChecklistItemStatus.ACTION_REQUIRED: "Consider offering a feeding.",
            ChecklistItemStatus.CHECK_NEEDED: "Baby may be getting hungry.",
            ChecklistItemStatus.OK: "Recently fed. Unlikely to be hungry."
        },
        ChecklistItemType.DIAPER: {
            ChecklistItemStatus.ACTION_REQUIRED: "Check diaper now",
            ChecklistItemStatus.CHECK_NEEDED: "Consider checking the diaper soon.",
            ChecklistItemStatus.OK: "Recently changed. Diaper is likely still clean."
        },
        ChecklistItemType.SLEEP: {
            ChecklistItemStatus.ACTION_REQUIRED: "Baby may be overtired. Create a calm environment for sleep.",
            ChecklistItemStatus.CHECK_NEEDED: "Watch for tired cues. May need sleep soon.",
            ChecklistItemStatus.OK: "Recently woke up. Baby should be well-rested."
        },
        ChecklistItemType.GAS_RELIEF: {
            ChecklistItemStatus.ACTION_REQUIRED: "Try burping positions or bicycle legs to relieve gas.",
            ChecklistItemStatus.CHECK_NEEDED: "If baby seems uncomfortable, try gentle tummy massage.",
            ChecklistItemStatus.OK: "Gas is less likely if baby was burped after last feeding."
        },
        ChecklistItemType.COMFORT: {
            ChecklistItemStatus.ACTION_REQUIRED: "Try skin-to-skin contact or swaddling for comfort.",
            ChecklistItemStatus.CHECK_NEEDED: "Consider if baby needs cuddles or soothing.",
            ChecklistItemStatus.OK: "Offer comfort through holding or gentle touch."
        },
        ChecklistItemType.ENVIRONMENT: {
            ChecklistItemStatus.ACTION_REQUIRED: "Move to a quiet, dim room to reduce stimulation.",
            ChecklistItemStatus.CHECK_NEEDED: "Check if environment is too stimulating.",
            ChecklistItemStatus.OK: "Ensure environment remains calm and soothing."
        }
    }

    return suggestions.get(item_type, {}).get(status, "Monitor baby's cues")


def get_care_metrics(
        db: Session,
        baby_ids: List[int],
        timeframe: str,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Calculate care sharing metrics for specified babies.

    Args:
        db: Database session
        baby_ids: List of baby IDs to calculate metrics for
        timeframe: Time period to analyze
        custom_start: Optional custom start date
        custom_end: Optional custom end date

    Returns:
        Dictionary containing care metrics by caregiver and activity type
    """
    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)

    # Initialize metrics structure
    metrics = _initialize_care_metrics(db, baby_ids)

    # Activity counting configurations
    activity_configs = [
        (Feeding, 'feeding', 'start_time'),
        (Sleep, 'sleep', 'start_time'),
        (Diaper, 'diaper', 'time'),
        (Health, 'health', 'time'),
        (Medication, 'medication', 'time_given'),
        (DoctorVisit, 'doctor_visit', 'visit_date'),
        (Growth, 'growth', 'measurement_date'),
        (Milestone, 'milestone', 'achieved_date'),
        (Photo, 'photo', 'date_taken'),
    ]

    # Count activities for each type
    for model, activity_type, time_field in activity_configs:
        _count_activities(
            db, metrics, model, activity_type,
            baby_ids, time_field, start_date, end_date
        )

    # Count pumping sessions (user-specific, not baby-specific)
    _count_pumping_sessions(db, metrics, list(metrics['by_caregiver'].keys()), start_date, end_date)

    # Calculate percentages
    _calculate_care_percentages(metrics)

    return metrics


def get_feeding_stats(
        db: Session,
        baby_ids: List[int],
        timeframe: str,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Calculate feeding statistics for specified babies.

    Args:
        db: Database session
        baby_ids: List of baby IDs to calculate stats for
        timeframe: Time period to analyze
        custom_start: Optional custom start date
        custom_end: Optional custom end date

    Returns:
        Dictionary containing feeding statistics
    """
    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)

    # Get all feedings in the timeframe
    feedings = db.query(Feeding).filter(
        Feeding.baby_id.in_(baby_ids),
        Feeding.start_time.between(start_date, end_date)
    ).all()

    # Initialize statistics
    stats = {
        'total_feedings': len(feedings),
        'by_type': defaultdict(int),
        'by_baby': defaultdict(lambda: defaultdict(int)),
        'average_duration': 0,
        'average_amount': 0,
        'daily_average': 0,
        'feeding_intervals': [],
        'last_feeding': None
    }

    if not feedings:
        return stats

    # Process feeding data
    total_duration = 0
    total_amount = 0
    amount_count = 0

    # Sort feedings by time for interval calculation
    sorted_feedings = sorted(feedings, key=lambda f: f.start_time)

    for i, feeding in enumerate(sorted_feedings):
        # Count by type
        feeding_type = feeding.feeding_type.value if hasattr(feeding.feeding_type, 'value') else str(
            feeding.feeding_type)
        stats['by_type'][feeding_type] += 1

        # Count by baby
        stats['by_baby'][feeding.baby_id][feeding_type] += 1

        # Sum durations and amounts
        if feeding.duration:
            total_duration += feeding.duration
        if feeding.amount:
            total_amount += feeding.amount
            amount_count += 1

        # Calculate intervals between feedings
        if i > 0 and sorted_feedings[i - 1].baby_id == feeding.baby_id:
            interval = (feeding.start_time - sorted_feedings[i - 1].start_time).total_seconds() / 3600
            stats['feeding_intervals'].append(round(interval, 1))

    # Calculate averages
    stats['average_duration'] = round(total_duration / len(feedings), 1) if feedings else 0
    stats['average_amount'] = round(total_amount / amount_count, 1) if amount_count > 0 else 0

    # Calculate daily average
    days = max((end_date - start_date).days, 1)
    stats['daily_average'] = round(len(feedings) / days, 1)

    # Average feeding interval
    if stats['feeding_intervals']:
        stats['average_interval_hours'] = round(sum(stats['feeding_intervals']) / len(stats['feeding_intervals']), 1)
    else:
        stats['average_interval_hours'] = 0

    # Get last feeding info
    last_feeding = sorted_feedings[-1] if sorted_feedings else None
    if last_feeding:
        baby = db.query(Baby).filter(Baby.id == last_feeding.baby_id).first()
        stats['last_feeding'] = {
            'time': last_feeding.start_time,
            'baby_name': baby.fullname if baby else "Unknown",
            'type': feeding_type,
            'time_ago_hours': round((datetime.utcnow() - last_feeding.start_time).total_seconds() / 3600, 1)
        }

    # Convert defaultdicts to regular dicts for JSON serialization
    stats['by_type'] = dict(stats['by_type'])
    stats['by_baby'] = {k: dict(v) for k, v in stats['by_baby'].items()}

    return stats


def get_sleep_patterns(
        db: Session,
        baby_ids: List[int],
        timeframe: str,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Analyze sleep patterns for specified babies.

    Args:
        db: Database session
        baby_ids: List of baby IDs to analyze
        timeframe: Time period to analyze
        custom_start: Optional custom start date
        custom_end: Optional custom end date

    Returns:
        Dictionary containing sleep pattern analysis
    """
    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)
    days = max((end_date - start_date).days, 1)

    # If analyzing a single baby, use the specialized sleep analysis
    if len(baby_ids) == 1:
        # Use the existing comprehensive sleep analysis function
        from app.main.service.baby_service import get_baby_if_authorized
        baby = get_baby_if_authorized(db, baby_ids[0], db.query(User).first().id)
        if not isinstance(baby, dict):  # If authorized
            return get_sleep_analysis(db, baby_ids[0], baby.parent_id, days, "custom")

    # For multiple babies, provide aggregated analysis
    sleep_records = db.query(Sleep).filter(
        Sleep.baby_id.in_(baby_ids),
        Sleep.start_time.between(start_date, end_date)
    ).all()

    # Initialize pattern analysis
    patterns = {
        'total_sleep_sessions': len(sleep_records),
        'by_baby': defaultdict(lambda: {
            'total_sessions': 0,
            'total_duration_minutes': 0,
            'average_duration_minutes': 0,
            'night_sleep_minutes': 0,
            'day_sleep_minutes': 0,
            'sleep_quality_distribution': defaultdict(int)
        }),
        'by_time_of_day': {
            'night': 0,  # 7pm - 7am
            'morning': 0,  # 7am - 12pm
            'afternoon': 0,  # 12pm - 5pm
            'evening': 0  # 5pm - 7pm
        },
        'average_sleep_per_day': 0,
        'longest_sleep': None,
        'shortest_sleep': None
    }

    total_duration = 0

    for sleep in sleep_records:
        if not sleep.duration:
            continue

        baby_stats = patterns['by_baby'][sleep.baby_id]
        baby_stats['total_sessions'] += 1
        baby_stats['total_duration_minutes'] += sleep.duration
        total_duration += sleep.duration

        # Categorize by time of day
        hour = sleep.start_time.hour
        if 19 <= hour or hour < 7:
            patterns['by_time_of_day']['night'] += 1
            baby_stats['night_sleep_minutes'] += sleep.duration
        elif 7 <= hour < 12:
            patterns['by_time_of_day']['morning'] += 1
            baby_stats['day_sleep_minutes'] += sleep.duration
        elif 12 <= hour < 17:
            patterns['by_time_of_day']['afternoon'] += 1
            baby_stats['day_sleep_minutes'] += sleep.duration
        else:
            patterns['by_time_of_day']['evening'] += 1
            baby_stats['day_sleep_minutes'] += sleep.duration

        # Track quality distribution
        if sleep.quality:
            quality = sleep.quality.value if hasattr(sleep.quality, 'value') else str(sleep.quality)
            baby_stats['sleep_quality_distribution'][quality] += 1

        # Track longest and shortest sleep
        if not patterns['longest_sleep'] or sleep.duration > patterns['longest_sleep']['duration']:
            patterns['longest_sleep'] = {
                'duration': sleep.duration,
                'baby_id': sleep.baby_id,
                'start_time': sleep.start_time
            }

        if not patterns['shortest_sleep'] or sleep.duration < patterns['shortest_sleep']['duration']:
            patterns['shortest_sleep'] = {
                'duration': sleep.duration,
                'baby_id': sleep.baby_id,
                'start_time': sleep.start_time
            }

    # Calculate averages
    patterns['average_sleep_per_day'] = round(total_duration / days, 1) if days > 0 else 0

    # Calculate per-baby averages
    for baby_id, stats in patterns['by_baby'].items():
        if stats['total_sessions'] > 0:
            stats['average_duration_minutes'] = round(
                stats['total_duration_minutes'] / stats['total_sessions'], 1
            )
        stats['sleep_quality_distribution'] = dict(stats['sleep_quality_distribution'])

    # Convert defaultdicts to regular dicts
    patterns['by_baby'] = dict(patterns['by_baby'])

    return patterns


def get_growth_data(
        db: Session,
        baby_ids: List[int],
        timeframe: str,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get growth measurement data for specified babies.

    Args:
        db: Database session
        baby_ids: List of baby IDs to get growth data for
        timeframe: Time period to query
        custom_start: Optional custom start date
        custom_end: Optional custom end date

    Returns:
        Dictionary containing growth data and trends
    """
    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)

    # Get growth records
    growth_records = db.query(Growth).filter(
        Growth.baby_id.in_(baby_ids),
        Growth.measurement_date.between(start_date, end_date)
    ).order_by(Growth.measurement_date).all()

    # Initialize growth data structure
    growth_data = {
        'total_measurements': len(growth_records),
        'by_baby': defaultdict(lambda: {
            'measurements': [],
            'latest': None,
            'weight_change': None,
            'height_change': None,
            'trend': {
                'weight': 'stable',
                'height': 'stable'
            }
        })
    }

    # Process growth records by baby
    for baby_id in baby_ids:
        baby_records = [g for g in growth_records if g.baby_id == baby_id]
        if not baby_records:
            continue

        baby_data = growth_data['by_baby'][baby_id]

        # Store all measurements
        for record in baby_records:
            measurement = {
                'date': record.measurement_date,
                'weight': record.weight,
                'height': record.height,
                'notes': record.notes
            }
            baby_data['measurements'].append(measurement)

        # Get latest measurement
        latest = baby_records[-1]
        baby_data['latest'] = {
            'date': latest.measurement_date,
            'weight': latest.weight,
            'height': latest.height
        }

        # Calculate changes if we have at least 2 measurements
        if len(baby_records) >= 2:
            first = baby_records[0]

            # Weight change
            if first.weight and latest.weight:
                baby_data['weight_change'] = round(latest.weight - first.weight, 2)
                baby_data['trend']['weight'] = 'increasing' if baby_data['weight_change'] > 0 else 'decreasing'

            # Height change
            if first.height and latest.height:
                baby_data['height_change'] = round(latest.height - first.height, 1)
                baby_data['trend']['height'] = 'increasing' if baby_data['height_change'] > 0 else 'decreasing'

    # Convert defaultdict to regular dict
    growth_data['by_baby'] = dict(growth_data['by_baby'])

    # Add summary statistics
    if growth_records:
        weights = [g.weight for g in growth_records if g.weight]
        heights = [g.height for g in growth_records if g.height]

        growth_data['summary'] = {
            'average_weight': round(sum(weights) / len(weights), 2) if weights else None,
            'average_height': round(sum(heights) / len(heights), 1) if heights else None,
            'measurement_frequency_days': round(
                (end_date - start_date).days / len(growth_records), 1
            ) if len(growth_records) > 1 else None
        }

    return growth_data


def get_timeframe_dates(
        timeframe: str,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None
) -> tuple:
    """
    Calculate start and end dates based on timeframe.

    Args:
        timeframe: Timeframe string (TODAY, WEEK, MONTH, CUSTOM)
        custom_start: Optional custom start date
        custom_end: Optional custom end date

    Returns:
        Tuple of (start_date, end_date)
    """
    now = datetime.utcnow()

    if timeframe == TimeFrame.TODAY:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif timeframe == TimeFrame.WEEK:
        start_date = now - timedelta(days=7)
        end_date = now
    elif timeframe == TimeFrame.MONTH:
        start_date = now - timedelta(days=30)
        end_date = now
    elif timeframe == TimeFrame.CUSTOM and custom_start and custom_end:
        start_date = custom_start
        end_date = custom_end
    else:
        # Default to week
        start_date = now - timedelta(days=7)
        end_date = now

    return start_date, end_date


# Helper functions
def _get_default_widgets_config() -> List[Dict[str, Any]]:
    """Return default widget configuration."""
    return [
        {"type": WidgetType.UPCOMING_EVENTS, "position": 0, "enabled": True, "timeframe": TimeFrame.WEEK},
        {"type": WidgetType.RECENT_ACTIVITIES, "position": 1, "enabled": True, "timeframe": TimeFrame.WEEK},
        {"type": WidgetType.CARE_METRICS, "position": 2, "enabled": True, "timeframe": TimeFrame.MONTH},
        {"type": WidgetType.FEEDING_STATS, "position": 3, "enabled": True, "timeframe": TimeFrame.WEEK},
        {"type": WidgetType.SLEEP_PATTERNS, "position": 4, "enabled": True, "timeframe": TimeFrame.WEEK},
        {"type": WidgetType.GROWTH_CHART, "position": 5, "enabled": True, "timeframe": TimeFrame.MONTH}
    ]


def _normalize_widget_config(widget: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a widget configuration dictionary."""
    return {
        "type": widget.get('type'),
        "position": widget.get('position'),
        "enabled": widget.get('enabled', True),
        "timeframe": widget.get('timeframe', TimeFrame.WEEK),
        "custom_settings": widget.get('custom_settings', {})
    }


def _get_baby_ids_for_dashboard(babies: List[Baby], baby_id: Optional[int]) -> List[int]:
    """Get list of baby IDs to use for dashboard data."""
    baby_ids = [baby.id for baby in babies]
    if baby_id and baby_id in baby_ids:
        return [baby_id]
    return baby_ids


def _serialize_babies(babies: List[Baby]) -> List[Dict[str, Any]]:
    """Serialize baby objects to dictionaries."""
    serialized = []
    for baby in babies:
        baby_dict = {
            'id': baby.id,
            'created_at': baby.created_at,
            'fullname': baby.fullname,
            'birthdate': baby.birthdate,
            'weight': baby.weight,
            'height': baby.height,
            'sex': baby.sex.value if baby.sex else None,
            'picture': baby.picture,
            'picture_url': getattr(baby, 'picture_url', None),
            'parent_id': baby.parent_id
        }

        # Add parent info if available
        if hasattr(baby, 'parent') and baby.parent:
            baby_dict['parent'] = {
                'id': baby.parent.id,
                'name': baby.parent.name,
                'email': baby.parent.email,
                'picture': baby.parent.picture
            }

        # Add coparents info if available
        if hasattr(baby, 'coparents') and baby.coparents:
            baby_dict['coparents'] = [{
                'id': coparent.id,
                'name': coparent.name,
                'email': coparent.email,
                'picture': coparent.picture
            } for coparent in baby.coparents]

        serialized.append(baby_dict)

    return serialized


def _serialize_preferences(preferences: DashboardPreference) -> Dict[str, Any]:
    """Serialize dashboard preferences to dictionary."""
    return {
        'id': preferences.id,
        'created_at': preferences.created_at,
        'user_id': preferences.user_id,
        'layout_type': preferences.layout_type,
        'default_baby_id': preferences.default_baby_id,
        'default_timeframe': preferences.default_timeframe,
        'widgets_config': preferences.widgets_config
    }


def _get_widget_data(
        db: Session,
        preferences: DashboardPreference,
        baby_ids: List[int],
        timeframe: str,
        custom_start: Optional[datetime],
        custom_end: Optional[datetime]
) -> List[Dict[str, Any]]:
    """Get data for all enabled widgets."""
    widgets = []

    # Get enabled widgets sorted by position
    enabled_widgets = [
        w for w in preferences.widgets_config
        if isinstance(w, dict) and w.get('enabled', True)
    ]
    enabled_widgets.sort(key=lambda w: w.get('position', 0))

    # Widget data fetchers
    widget_fetchers = {
        WidgetType.RECENT_ACTIVITIES: lambda tf, cs, ce: get_recent_activities(
            db, baby_ids, tf, cs, ce, limit=10
        ),
        WidgetType.UPCOMING_EVENTS: lambda tf, cs, ce: get_baby_care_checklist(
            db, baby_ids
        ),
        WidgetType.CARE_METRICS: lambda tf, cs, ce: get_care_metrics(
            db, baby_ids, tf, cs, ce
        ),
        WidgetType.FEEDING_STATS: lambda tf, cs, ce: get_feeding_stats(
            db, baby_ids, tf, cs, ce
        ),
        WidgetType.SLEEP_PATTERNS: lambda tf, cs, ce: get_sleep_patterns(
            db, baby_ids, tf, cs, ce
        ),
        WidgetType.GROWTH_CHART: lambda tf, cs, ce: get_growth_data(
            db, baby_ids, tf, cs, ce
        ),
        WidgetType.MILESTONE_TIMELINE: lambda tf, cs, ce: get_milestone_timeline(
            db, baby_ids, tf, cs, ce
        ),
        WidgetType.PHOTO_GALLERY: lambda tf, cs, ce: get_photo_gallery(
            db, baby_ids, tf, cs, ce
        )
    }

    # Process each widget
    for widget_config in enabled_widgets:
        widget_type = widget_config.get('type')
        widget_timeframe = widget_config.get('timeframe', timeframe)

        # Handle custom timeframe for widgets
        widget_custom_start = custom_start
        widget_custom_end = custom_end

        if widget_timeframe == TimeFrame.CUSTOM:
            # Check if widget has its own custom dates in custom_settings
            custom_settings = widget_config.get('custom_settings', {})
            if custom_settings.get('custom_start_date') and custom_settings.get('custom_end_date'):
                # Parse custom dates from widget settings
                widget_custom_start = custom_settings['custom_start_date']
                widget_custom_end = custom_settings['custom_end_date']

                # Convert string dates to datetime if needed
                if isinstance(widget_custom_start, str):
                    widget_custom_start = datetime.fromisoformat(widget_custom_start.replace('Z', '+00:00'))
                if isinstance(widget_custom_end, str):
                    widget_custom_end = datetime.fromisoformat(widget_custom_end.replace('Z', '+00:00'))
            # Otherwise fall back to dashboard-level custom dates
            elif widget_timeframe == TimeFrame.CUSTOM and not widget_custom_start:
                # Use preference-level custom dates
                widget_custom_start = preferences.custom_start_date
                widget_custom_end = preferences.custom_end_date

        widget = {
            'type': widget_type,
            'timeframe': widget_timeframe,
            'position': widget_config.get('position', 0),
            'data': None
        }

        # Get widget data using appropriate fetcher
        if widget_type in widget_fetchers:
            widget['data'] = widget_fetchers[widget_type](
                widget_timeframe, widget_custom_start, widget_custom_end
            )

        widgets.append(widget)

    return widgets


def _create_activity_entry(
        db: Session,
        record: Any,
        activity_type: str,
        time: datetime,
        details_formatter: callable
) -> Dict[str, Any]:
    """Create a standardized activity entry."""
    baby = db.query(Baby).filter(Baby.id == record.baby_id).first()
    user = db.query(User).filter(User.id == record.recorded_by).first()

    return {
        'id': record.id,
        'type': activity_type,
        'time': time,
        'baby_id': record.baby_id,
        'baby_name': baby.fullname if baby else "Unknown",
        'caregiver_id': baby.parent_id if baby else None,
        'caregiver_name': user.name if user else "Unknown",
        'details': details_formatter(record)
    }


def _create_event_entry(
        db: Session,
        record: Any,
        event_type: str,
        time: datetime,
        details_formatter: callable
) -> Dict[str, Any]:
    """Create a standardized event entry."""
    baby = db.query(Baby).filter(Baby.id == record.baby_id).first()

    return {
        'id': record.id,
        'type': event_type,
        'time': time,
        'baby_id': record.baby_id,
        'baby_name': baby.fullname if baby else "Unknown",
        'details': details_formatter(record)
    }


def _format_feeding_details(feeding: Feeding) -> Dict[str, Any]:
    """Format feeding details for activity entry."""
    return {
        'feeding_type': feeding.feeding_type,
        'amount': feeding.amount,
        'duration': feeding.duration
    }


def _format_sleep_details(sleep: Sleep) -> Dict[str, Any]:
    """Format sleep details for activity entry."""
    return {
        'duration': sleep.duration,
        'quality': sleep.quality,
        'location': sleep.location
    }


def _format_diaper_details(diaper: Diaper) -> Dict[str, Any]:
    """Format diaper details for activity entry."""
    return {
        'content': diaper.content,
        'consistency': diaper.consistency,
        'color': diaper.color
    }


def _format_health_details(health: Health) -> Dict[str, Any]:
    """Format health details for activity entry."""
    return {
        'temperature': health.temperature,
        'symptoms': health.symptoms,
        'medication': health.medication
    }


def _format_doctor_visit_details(visit: DoctorVisit) -> Dict[str, Any]:
    """Format doctor visit details for event entry."""
    return {
        'doctor_name': visit.doctor_name,
        'visit_type': visit.visit_type,
        'reason': visit.reason
    }


def _format_medication_details(medication: Medication) -> Dict[str, Any]:
    """Format medication details for event entry."""
    return {
        'name': medication.name,
        'dosage': medication.dosage,
        'dosage_unit': medication.dosage_unit,
        'route': medication.route
    }


def _initialize_care_metrics(db: Session, baby_ids: List[int]) -> Dict[str, Any]:
    """Initialize care metrics structure with all caregivers."""
    metrics = {
        'total_activities': 0,
        'by_caregiver': {},
        'by_activity_type': {
            'feeding': {'total': 0, 'by_caregiver': {}},
            'sleep': {'total': 0, 'by_caregiver': {}},
            'diaper': {'total': 0, 'by_caregiver': {}},
            'health': {'total': 0, 'by_caregiver': {}},
            'medication': {'total': 0, 'by_caregiver': {}},
            'doctor_visit': {'total': 0, 'by_caregiver': {}},
            'growth': {'total': 0, 'by_caregiver': {}},
            'milestone': {'total': 0, 'by_caregiver': {}},
            'photo': {'total': 0, 'by_caregiver': {}},
            'pumping': {'total': 0, 'by_caregiver': {}}
        }
    }

    # Get all caregivers for these babies
    caregivers = {}
    for baby_id in baby_ids:
        baby = db.query(Baby).filter(Baby.id == baby_id).first()
        if baby:
            # Primary parent
            parent = db.query(User).filter(User.id == baby.parent_id).first()
            if parent:
                caregivers[parent.id] = {
                    'id': parent.id,
                    'name': parent.name or parent.email,
                    'email': parent.email,
                    'picture': parent.picture,
                    'is_primary': True
                }

            # Co-parents
            for coparent in baby.coparents:
                caregivers[coparent.id] = {
                    'id': coparent.id,
                    'name': coparent.name or coparent.email,
                    'email': coparent.email,
                    'picture': coparent.picture,
                    'is_primary': False
                }

    # Initialize metrics for each caregiver
    for caregiver_id, caregiver_info in caregivers.items():
        metrics['by_caregiver'][caregiver_id] = {
            'caregiver': caregiver_info,
            'total': 0,
            'percentage': 0,
            'by_activity_type': {
                activity_type: 0
                for activity_type in metrics['by_activity_type']
            }
        }

        for activity_type in metrics['by_activity_type']:
            metrics['by_activity_type'][activity_type]['by_caregiver'][caregiver_id] = 0

    return metrics


def _count_activities(
        db: Session,
        metrics: Dict[str, Any],
        model: Any,
        activity_type: str,
        baby_ids: List[int],
        time_field: str,
        start_date: datetime,
        end_date: datetime
):
    """Count activities of a specific type and update metrics."""
    records = db.query(model).filter(
        model.baby_id.in_(baby_ids),
        getattr(model, time_field).between(start_date, end_date)
    ).all()

    for record in records:
        caregiver_id = record.recorded_by
        metrics['total_activities'] += 1
        metrics['by_activity_type'][activity_type]['total'] += 1

        if caregiver_id in metrics['by_caregiver']:
            metrics['by_caregiver'][caregiver_id]['total'] += 1
            metrics['by_caregiver'][caregiver_id]['by_activity_type'][activity_type] += 1
            metrics['by_activity_type'][activity_type]['by_caregiver'][caregiver_id] += 1


def _count_pumping_sessions(
        db: Session,
        metrics: Dict[str, Any],
        caregiver_ids: List[int],
        start_date: datetime,
        end_date: datetime
):
    """Count pumping sessions for caregivers."""
    pumpings = db.query(Pumping).filter(
        Pumping.user_id.in_(caregiver_ids),
        Pumping.start_time.between(start_date, end_date)
    ).all()

    for pumping in pumpings:
        caregiver_id = pumping.user_id
        metrics['total_activities'] += 1
        metrics['by_activity_type']['pumping']['total'] += 1

        if caregiver_id in metrics['by_caregiver']:
            metrics['by_caregiver'][caregiver_id]['total'] += 1
            metrics['by_caregiver'][caregiver_id]['by_activity_type']['pumping'] += 1
            metrics['by_activity_type']['pumping']['by_caregiver'][caregiver_id] += 1


def _calculate_care_percentages(metrics: Dict[str, Any]):
    """Calculate percentage contributions for each caregiver."""
    if metrics['total_activities'] > 0:
        for caregiver_id in metrics['by_caregiver']:
            caregiver_total = metrics['by_caregiver'][caregiver_id]['total']
            metrics['by_caregiver'][caregiver_id]['percentage'] = round(
                (caregiver_total / metrics['total_activities']) * 100, 1
            )


def get_milestone_timeline(
        db: Session,
        baby_ids: List[int],
        timeframe: str,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get milestone timeline data for specified babies.

    Args:
        db: Database session
        baby_ids: List of baby IDs to get milestones for
        timeframe: Time period to query
        custom_start: Optional custom start date
        custom_end: Optional custom end date

    Returns:
        Dictionary containing milestone timeline data
    """
    from app.main.service.milestone_service import get_milestones_for_baby

    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)

    # Initialize timeline structure
    timeline_data = {
        'total_milestones': 0,
        'by_baby': defaultdict(lambda: {
            'milestones': [],
            'by_category': defaultdict(int),
            'recent_milestone': None
        }),
        'by_category': defaultdict(int),
        'milestones_by_month': defaultdict(list)
    }

    # Get milestones for each baby
    for baby_id in baby_ids:
        # Get the first user as the current user ID (from the caregivers)
        baby = db.query(Baby).filter(Baby.id == baby_id).first()
        if not baby:
            continue

        user_id = baby.parent_id

        # Get milestones using the existing service
        milestones = get_milestones_for_baby(
            db, baby_id, user_id,
            skip=0, limit=100,
            start_date=start_date,
            end_date=end_date
        )

        # Skip if error response
        if isinstance(milestones, dict):
            continue

        baby_data = timeline_data['by_baby'][baby_id]

        for milestone in milestones:
            # Format milestone for timeline
            milestone_dict = {
                'id': milestone.id,
                'title': milestone.title,
                'category': milestone.category,
                'achieved_date': milestone.achieved_date,
                'description': milestone.description,
                'notes': milestone.notes,
                'photo_url': milestone.photo_url,
                'baby_id': baby_id,
                'baby_name': baby.fullname,
                'caregiver_name': getattr(milestone, 'caregiver_name', None)
            }

            baby_data['milestones'].append(milestone_dict)
            timeline_data['total_milestones'] += 1

            # Count by category
            category = milestone.category.value if hasattr(milestone.category, 'value') else str(milestone.category)
            baby_data['by_category'][category] += 1
            timeline_data['by_category'][category] += 1

            # Group by month for timeline visualization
            month_key = milestone.achieved_date.strftime('%Y-%m')
            timeline_data['milestones_by_month'][month_key].append(milestone_dict)

        # Get most recent milestone for this baby
        if baby_data['milestones']:
            baby_data['recent_milestone'] = baby_data['milestones'][0]  # Already sorted by date desc

    # Convert defaultdicts to regular dicts
    timeline_data['by_baby'] = dict(timeline_data['by_baby'])
    timeline_data['by_category'] = dict(timeline_data['by_category'])
    timeline_data['milestones_by_month'] = dict(timeline_data['milestones_by_month'])

    # Sort milestones by month
    for month in timeline_data['milestones_by_month']:
        timeline_data['milestones_by_month'][month].sort(
            key=lambda x: x['achieved_date'],
            reverse=True
        )

    return timeline_data


from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from collections import defaultdict


def normalize_datetime(dt):
    """
    Normalize datetime to timezone-aware UTC.
    If datetime is naive, assume it's in UTC.
    """
    if dt is None:
        return None

    if isinstance(dt, str):
        # If it's a string, try to parse it
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            # Try other common formats if needed
            try:
                dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return None

    if dt.tzinfo is None:
        # If naive, assume UTC
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC if not already
        dt = dt.astimezone(timezone.utc)

    return dt


def get_photo_gallery(
        db: Session,
        baby_ids: List[int],
        timeframe: str,
        custom_start: Optional[datetime] = None,
        custom_end: Optional[datetime] = None,
        limit: int = 20
) -> Dict[str, Any]:
    """
    Get photo gallery data for specified babies.

    Args:
        db: Database session
        baby_ids: List of baby IDs to get photos for
        timeframe: Time period to query
        custom_start: Optional custom start date
        custom_end: Optional custom end date
        limit: Maximum number of photos to return per baby

    Returns:
        Dictionary containing photo gallery data
    """
    from app.main.service.photo_service import get_baby_photos

    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)

    # Normalize the start and end dates
    start_date = normalize_datetime(start_date)
    end_date = normalize_datetime(end_date)

    # Initialize gallery structure
    gallery_data = {
        'total_photos': 0,
        'by_baby': defaultdict(lambda: {
            'photos': [],
            'by_type': defaultdict(int),
            'latest_photo': None
        }),
        'by_type': defaultdict(int),
        'recent_photos': []
    }

    all_photos = []

    # Get photos for each baby
    for baby_id in baby_ids:
        # Get the baby to get user_id
        baby = db.query(Baby).filter(Baby.id == baby_id).first()
        if not baby:
            continue

        user_id = baby.parent_id

        # Get photos using the existing service
        photos = get_baby_photos(db, baby_id, user_id)

        # Skip if error response
        if isinstance(photos, dict) and 'status' in photos and photos['status'] == 'fail':
            continue

        baby_data = gallery_data['by_baby'][baby_id]

        # Filter photos by date range
        for photo in photos:
            photo_date_raw = photo.get('date_taken') or photo.get('created_at')
            photo_date = normalize_datetime(photo_date_raw)

            # Apply date filter - only compare if all dates are valid
            if photo_date and start_date and end_date:
                if start_date <= photo_date <= end_date:
                    # Add baby name to photo data
                    photo['baby_name'] = baby.fullname

                    baby_data['photos'].append(photo)
                    all_photos.append(photo)
                    gallery_data['total_photos'] += 1

                    # Count by type
                    photo_type = photo.get('photo_type', 'other')
                    baby_data['by_type'][photo_type] += 1
                    gallery_data['by_type'][photo_type] += 1
            elif not start_date or not end_date:
                # If date filtering isn't possible, include all photos
                photo['baby_name'] = baby.fullname
                baby_data['photos'].append(photo)
                all_photos.append(photo)
                gallery_data['total_photos'] += 1

                photo_type = photo.get('photo_type', 'other')
                baby_data['by_type'][photo_type] += 1
                gallery_data['by_type'][photo_type] += 1

        # Sort photos by date (newest first) and apply limit
        baby_data['photos'].sort(
            key=lambda x: normalize_datetime(x.get('date_taken') or x.get('created_at')) or datetime.min.replace(
                tzinfo=timezone.utc),
            reverse=True
        )
        baby_data['photos'] = baby_data['photos'][:limit]

        # Get latest photo for this baby
        if baby_data['photos']:
            baby_data['latest_photo'] = baby_data['photos'][0]

    # Get recent photos across all babies
    all_photos.sort(
        key=lambda x: normalize_datetime(x.get('date_taken') or x.get('created_at')) or datetime.min.replace(
            tzinfo=timezone.utc),
        reverse=True
    )
    gallery_data['recent_photos'] = all_photos[:limit]

    # Convert defaultdicts to regular dicts
    gallery_data['by_baby'] = dict(gallery_data['by_baby'])
    gallery_data['by_type'] = dict(gallery_data['by_type'])

    # Add summary statistics
    if gallery_data['total_photos'] > 0:
        gallery_data['summary'] = {
            'average_per_baby': round(gallery_data['total_photos'] / len(baby_ids), 1) if baby_ids else 0,
            'most_common_type': max(gallery_data['by_type'], key=gallery_data['by_type'].get) if gallery_data[
                'by_type'] else None
        }

    return gallery_data
