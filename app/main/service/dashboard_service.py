from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.main.model import Growth, Pumping
from app.main.model.baby import Baby
from app.main.model.dashboard import DashboardPreference, WidgetType, TimeFrame
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


def get_upcoming_events(db: Session, baby_ids: List[int], days_ahead: int = 7) -> List[Dict[str, Any]]:
    """
    Get upcoming events like doctor visits and scheduled medications.

    Args:
        db: Database session
        baby_ids: List of baby IDs to get events for
        days_ahead: Number of days to look ahead

    Returns:
        List of upcoming events sorted by time
    """
    now = datetime.utcnow()
    future_date = now + timedelta(days=days_ahead)
    events = []

    # Get upcoming doctor visits
    doctor_visits = db.query(DoctorVisit).filter(
        DoctorVisit.baby_id.in_(baby_ids),
        DoctorVisit.visit_date > now,
        DoctorVisit.visit_date <= future_date
    ).order_by(DoctorVisit.visit_date).all()

    for visit in doctor_visits:
        event = _create_event_entry(
            db, visit, 'doctor_visit',
            visit.visit_date,
            _format_doctor_visit_details
        )
        events.append(event)

    # Get upcoming medications
    medications = db.query(Medication).filter(
        Medication.baby_id.in_(baby_ids),
        Medication.time_given > now,
        Medication.time_given <= future_date
    ).order_by(Medication.time_given).all()

    for medication in medications:
        event = _create_event_entry(
            db, medication, 'medication',
            medication.time_given,
            _format_medication_details
        )
        events.append(event)

    # Sort by time ascending
    events.sort(key=lambda x: x['time'])
    return events


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
        WidgetType.UPCOMING_EVENTS: lambda tf, cs, ce: get_upcoming_events(
            db, baby_ids, days_ahead=7
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