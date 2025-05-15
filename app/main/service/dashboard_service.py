from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.main.model.baby import Baby
from app.main.model.dashboard import DashboardPreference, WidgetType, TimeFrame
from app.main.model.diaper import Diaper
from app.main.model.doctor_visit import DoctorVisit
from app.main.model.feeding import Feeding
from app.main.model.health import Health
from app.main.model.medication import Medication
from app.main.model.sleep import Sleep
from app.main.model.user import User
from app.main.service.baby_service import get_all_babies_for_user


def get_or_create_dashboard_preferences(db: Session, user_id: int) -> DashboardPreference:
    """Get existing dashboard preferences or create default ones"""
    preferences = db.query(DashboardPreference).filter(DashboardPreference.user_id == user_id).first()

    if preferences:
        # Ensure widgets_config is not None
        if preferences.widgets_config is None:
            preferences.widgets_config = default_widgets_config()
            db.commit()
        return preferences

    # Create default preferences with all widgets enabled
    default_widgets = default_widgets_config()

    new_preferences = DashboardPreference(
        user_id=user_id,
        layout_type="grid",
        default_timeframe=TimeFrame.WEEK,
        widgets_config=default_widgets
    )

    db.add(new_preferences)
    db.commit()
    db.refresh(new_preferences)
    return new_preferences

def default_widgets_config():
    """Return a default widget configuration"""
    return [
        {"type": WidgetType.UPCOMING_EVENTS, "position": 0, "enabled": True, "timeframe": TimeFrame.WEEK},
        {"type": WidgetType.RECENT_ACTIVITIES, "position": 1, "enabled": True, "timeframe": TimeFrame.WEEK},
        {"type": WidgetType.CARE_METRICS, "position": 2, "enabled": True, "timeframe": TimeFrame.MONTH},
        {"type": WidgetType.FEEDING_STATS, "position": 3, "enabled": True, "timeframe": TimeFrame.WEEK},
        {"type": WidgetType.SLEEP_PATTERNS, "position": 4, "enabled": True, "timeframe": TimeFrame.WEEK},
        {"type": WidgetType.GROWTH_CHART, "position": 5, "enabled": True, "timeframe": TimeFrame.MONTH}
    ]


def update_dashboard_preferences(db: Session, user_id: int, preferences_data: Dict[str, Any]) -> DashboardPreference:
    """Update dashboard preferences for a user"""
    preferences = get_or_create_dashboard_preferences(db, user_id)

    # Update the preferences
    preferences.layout_type = preferences_data.get('layout_type', preferences.layout_type)
    preferences.default_baby_id = preferences_data.get('default_baby_id', preferences.default_baby_id)
    preferences.default_timeframe = preferences_data.get('default_timeframe', preferences.default_timeframe)

    # Make sure we use widgets_config, not widgets
    if 'widgets_config' in preferences_data:
        preferences.widgets_config = [
            {
                "type": widget.get('type'),
                "position": widget.get('position'),
                "enabled": widget.get('enabled', True),
                "timeframe": widget.get('timeframe', TimeFrame.WEEK),
                "custom_settings": widget.get('custom_settings', {})
            }
            for widget in preferences_data['widgets_config']
        ]

    # For backward compatibility if someone sends 'widgets' instead of 'widgets_config'
    elif 'widgets' in preferences_data:
        preferences.widgets_config = [
            {
                "type": widget.get('type'),
                "position": widget.get('position'),
                "enabled": widget.get('enabled', True),
                "timeframe": widget.get('timeframe', TimeFrame.WEEK),
                "custom_settings": widget.get('custom_settings', {})
            }
            for widget in preferences_data['widgets']
        ]

    db.commit()
    db.refresh(preferences)
    return preferences


def get_timeframe_dates(timeframe: str, custom_start: Optional[datetime] = None,
                        custom_end: Optional[datetime] = None) -> tuple:
    """Calculate start and end dates based on timeframe"""
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
        # Default to week if invalid timeframe
        start_date = now - timedelta(days=7)
        end_date = now

    return start_date, end_date


def get_recent_activities(db: Session, baby_ids: List[int], timeframe: str,
                          custom_start: Optional[datetime] = None,
                          custom_end: Optional[datetime] = None,
                          limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent activities across all tracking categories for specified babies"""
    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)

    activities = []

    # Get recent feedings
    feedings = db.query(Feeding).filter(
        Feeding.baby_id.in_(baby_ids),
        Feeding.start_time.between(start_date, end_date)
    ).order_by(desc(Feeding.start_time)).limit(limit).all()

    for feeding in feedings:
        baby = db.query(Baby).filter(Baby.id == feeding.baby_id).first()
        user = db.query(User).filter(User.id == baby.parent_id).first()

        activities.append({
            'id': feeding.id,
            'type': 'feeding',
            'time': feeding.start_time,
            'baby_id': feeding.baby_id,
            'baby_name': baby.fullname if baby else "Unknown",
            'caregiver_id': baby.parent_id if baby else None,
            'caregiver_name': user.name if user else "Unknown",
            'details': {
                'feeding_type': feeding.feeding_type,
                'amount': feeding.amount,
                'duration': feeding.duration
            }
        })

    # Get recent sleeps
    sleeps = db.query(Sleep).filter(
        Sleep.baby_id.in_(baby_ids),
        Sleep.start_time.between(start_date, end_date)
    ).order_by(desc(Sleep.start_time)).limit(limit).all()

    for sleep in sleeps:
        baby = db.query(Baby).filter(Baby.id == sleep.baby_id).first()
        user = db.query(User).filter(User.id == baby.parent_id).first()

        activities.append({
            'id': sleep.id,
            'type': 'sleep',
            'time': sleep.start_time,
            'baby_id': sleep.baby_id,
            'baby_name': baby.fullname if baby else "Unknown",
            'caregiver_id': baby.parent_id if baby else None,
            'caregiver_name': user.name if user else "Unknown",
            'details': {
                'duration': sleep.duration,
                'quality': sleep.quality,
                'location': sleep.location
            }
        })

    # Get recent diapers
    diapers = db.query(Diaper).filter(
        Diaper.baby_id.in_(baby_ids),
        Diaper.time.between(start_date, end_date)
    ).order_by(desc(Diaper.time)).limit(limit).all()

    for diaper in diapers:
        baby = db.query(Baby).filter(Baby.id == diaper.baby_id).first()
        user = db.query(User).filter(User.id == baby.parent_id).first()

        activities.append({
            'id': diaper.id,
            'type': 'diaper',
            'time': diaper.time,
            'baby_id': diaper.baby_id,
            'baby_name': baby.fullname if baby else "Unknown",
            'caregiver_id': baby.parent_id if baby else None,
            'caregiver_name': user.name if user else "Unknown",
            'details': {
                'content': diaper.content,
                'consistency': diaper.consistency,
                'color': diaper.color
            }
        })

    # Get recent health records
    health_records = db.query(Health).filter(
        Health.baby_id.in_(baby_ids),
        Health.time.between(start_date, end_date)
    ).order_by(desc(Health.time)).limit(limit).all()

    for health in health_records:
        baby = db.query(Baby).filter(Baby.id == health.baby_id).first()
        user = db.query(User).filter(User.id == baby.parent_id).first()

        activities.append({
            'id': health.id,
            'type': 'health',
            'time': health.time,
            'baby_id': health.baby_id,
            'baby_name': baby.fullname if baby else "Unknown",
            'caregiver_id': baby.parent_id if baby else None,
            'caregiver_name': user.name if user else "Unknown",
            'details': {
                'temperature': health.temperature,
                'symptoms': health.symptoms,
                'medication': health.medication
            }
        })

    # Sort all activities by time descending and limit to requested amount
    activities.sort(key=lambda x: x['time'], reverse=True)
    return activities[:limit]


def get_upcoming_events(db: Session, baby_ids: List[int], days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Get upcoming events like doctor visits and scheduled medications"""
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
        baby = db.query(Baby).filter(Baby.id == visit.baby_id).first()

        events.append({
            'id': visit.id,
            'type': 'doctor_visit',
            'time': visit.visit_date,
            'baby_id': visit.baby_id,
            'baby_name': baby.fullname if baby else "Unknown",
            'details': {
                'doctor_name': visit.doctor_name,
                'visit_type': visit.visit_type,
                'reason': visit.reason
            }
        })

    # Get upcoming medications (if they have a future scheduled time)
    medications = db.query(Medication).filter(
        Medication.baby_id.in_(baby_ids),
        Medication.time_given > now,
        Medication.time_given <= future_date
    ).order_by(Medication.time_given).all()

    for medication in medications:
        baby = db.query(Baby).filter(Baby.id == medication.baby_id).first()

        events.append({
            'id': medication.id,
            'type': 'medication',
            'time': medication.time_given,
            'baby_id': medication.baby_id,
            'baby_name': baby.fullname if baby else "Unknown",
            'details': {
                'name': medication.name,
                'dosage': medication.dosage,
                'dosage_unit': medication.dosage_unit,
                'route': medication.route
            }
        })

    # Sort events by time ascending
    events.sort(key=lambda x: x['time'])
    return events


def get_care_metrics(db: Session, baby_ids: List[int], timeframe: str,
                     custom_start: Optional[datetime] = None,
                     custom_end: Optional[datetime] = None) -> Dict[str, Any]:
    """Calculate care sharing metrics for specified babies"""
    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)

    # Initialize metrics structure
    metrics = {
        'total_activities': 0,
        'by_caregiver': {},
        'by_activity_type': {
            'feeding': {'total': 0, 'by_caregiver': {}},
            'sleep': {'total': 0, 'by_caregiver': {}},
            'diaper': {'total': 0, 'by_caregiver': {}},
            'health': {'total': 0, 'by_caregiver': {}},
            'medication': {'total': 0, 'by_caregiver': {}},
            'doctor_visit': {'total': 0, 'by_caregiver': {}}
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

    # Initialize metrics counters for each caregiver
    for caregiver_id, caregiver_info in caregivers.items():
        metrics['by_caregiver'][caregiver_id] = {
            'caregiver': caregiver_info,
            'total': 0,
            'percentage': 0,
            'by_activity_type': {
                'feeding': 0,
                'sleep': 0,
                'diaper': 0,
                'health': 0,
                'medication': 0,
                'doctor_visit': 0
            }
        }

        for activity_type in metrics['by_activity_type']:
            metrics['by_activity_type'][activity_type]['by_caregiver'][caregiver_id] = 0

    # Count feedings
    feedings = db.query(Feeding).filter(
        Feeding.baby_id.in_(baby_ids),
        Feeding.start_time.between(start_date, end_date)
    ).all()

    for feeding in feedings:
        caregiver_id = feeding.recorded_by
        metrics['total_activities'] += 1
        metrics['by_activity_type']['feeding']['total'] += 1

        if caregiver_id in metrics['by_caregiver']:
            metrics['by_caregiver'][caregiver_id]['total'] += 1
            metrics['by_caregiver'][caregiver_id]['by_activity_type']['feeding'] += 1
            metrics['by_activity_type']['feeding']['by_caregiver'][caregiver_id] += 1

    # Count sleeps
    sleeps = db.query(Sleep).filter(
        Sleep.baby_id.in_(baby_ids),
        Sleep.start_time.between(start_date, end_date)
    ).all()

    for sleep in sleeps:
        caregiver_id = sleep.recorded_by
        metrics['total_activities'] += 1
        metrics['by_activity_type']['sleep']['total'] += 1

        if caregiver_id in metrics['by_caregiver']:
            metrics['by_caregiver'][caregiver_id]['total'] += 1
            metrics['by_caregiver'][caregiver_id]['by_activity_type']['sleep'] += 1
            metrics['by_activity_type']['sleep']['by_caregiver'][caregiver_id] += 1

    # Count diapers
    diapers = db.query(Diaper).filter(
        Diaper.baby_id.in_(baby_ids),
        Diaper.time.between(start_date, end_date)
    ).all()

    for diaper in diapers:
        caregiver_id = diaper.recorded_by
        metrics['total_activities'] += 1
        metrics['by_activity_type']['diaper']['total'] += 1

        if caregiver_id in metrics['by_caregiver']:
            metrics['by_caregiver'][caregiver_id]['total'] += 1
            metrics['by_caregiver'][caregiver_id]['by_activity_type']['diaper'] += 1
            metrics['by_activity_type']['diaper']['by_caregiver'][caregiver_id] += 1

        # Count health
        healths = db.query(Health).filter(
            Health.baby_id.in_(baby_ids),
            Health.time.between(start_date, end_date)
        ).all()

        for health in healths:
            caregiver_id = health.recorded_by
            metrics['total_activities'] += 1
            metrics['by_activity_type']['health']['total'] += 1

            if caregiver_id in metrics['by_caregiver']:
                metrics['by_caregiver'][caregiver_id]['total'] += 1
                metrics['by_caregiver'][caregiver_id]['by_activity_type']['health'] += 1
                metrics['by_activity_type']['health']['by_caregiver'][caregiver_id] += 1


    #  'medication': {'total': 0, 'by_caregiver': {}},
    #  'doctor_visit': {'total': 0, 'by_caregiver': {}}

    # Calculate percentages
    if metrics['total_activities'] > 0:
        for caregiver_id in metrics['by_caregiver']:
            caregiver_total = metrics['by_caregiver'][caregiver_id]['total']
            metrics['by_caregiver'][caregiver_id]['percentage'] = round(
                (caregiver_total / metrics['total_activities']) * 100, 1
            )

    return metrics


def get_dashboard_data(db: Session, user_id: int, baby_id: Optional[int] = None,
                       timeframe: Optional[str] = None) -> Dict[str, Any]:
    """Get all dashboard data based on user preferences"""
    # Get user preferences
    preferences = get_or_create_dashboard_preferences(db, user_id)

    # If no specific timeframe is provided, use the default from preferences
    if not timeframe:
        timeframe = preferences.default_timeframe

    # If no baby_id is specified and there's a default baby in preferences, use it
    if not baby_id and preferences.default_baby_id:
        baby_id = preferences.default_baby_id

    # Get all babies the user has access to
    babies = get_all_babies_for_user(db, user_id)

    # Filter to specific baby if requested
    baby_ids = [baby.id for baby in babies]
    if baby_id and baby_id in baby_ids:
        baby_ids = [baby_id]

    # Convert babies to serializable dictionaries
    serialized_babies = []
    for baby in babies:
        serialized_baby = {
            'id': baby.id,
            'created_at': baby.created_at,
            'fullname': baby.fullname,
            'birthdate': baby.birthdate,
            'weight': baby.weight,
            'height': baby.height,
            'sex': baby.sex.value if baby.sex else None,
            'picture': baby.picture,
            'picture_url': baby.picture_url if hasattr(baby, 'picture_url') else None,
            'parent_id': baby.parent_id
        }
        # Add parent info if available
        if hasattr(baby, 'parent') and baby.parent:
            serialized_baby['parent'] = {
                'id': baby.parent.id,
                'name': baby.parent.name,
                'email': baby.parent.email,
                'picture': baby.parent.picture
            }

        # Add coparents info if available
        if hasattr(baby, 'coparents') and baby.coparents:
            serialized_baby['coparents'] = []
            for coparent in baby.coparents:
                serialized_baby['coparents'].append({
                    'id': coparent.id,
                    'name': coparent.name,
                    'email': coparent.email,
                    'picture': coparent.picture
                })

        serialized_babies.append(serialized_baby)

    # Convert preferences to serializable dictionary
    serialized_preferences = {
        'id': preferences.id,
        'created_at': preferences.created_at,
        'user_id': preferences.user_id,
        'layout_type': preferences.layout_type,
        'default_baby_id': preferences.default_baby_id,
        'default_timeframe': preferences.default_timeframe,
        'widgets_config': preferences.widgets_config
    }

    # Initialize dashboard data structure
    dashboard_data = {
        'babies': serialized_babies,  # Now these are dictionaries, not SQLAlchemy models
        'preferences': serialized_preferences,  # Now this is a dictionary, not a SQLAlchemy model
        'widgets': []
    }

    # Get enabled widgets from preferences
    enabled_widgets = [
        w for w in preferences.widgets_config
        if isinstance(w, dict) and w.get('enabled', True)
    ]

    # Sort widgets by position
    enabled_widgets.sort(key=lambda w: w.get('position', 0))

    # Process each widget
    for widget_config in enabled_widgets:
        widget_type = widget_config.get('type')
        widget_timeframe = widget_config.get('timeframe', timeframe)

        widget = {
            'type': widget_type,
            'timeframe': widget_timeframe,
            'position': widget_config.get('position', 0),
            'data': None
        }

        # Get widget-specific data
        if widget_type == WidgetType.RECENT_ACTIVITIES:
            widget['data'] = get_recent_activities(
                db, baby_ids, widget_timeframe, limit=10
            )
        elif widget_type == WidgetType.UPCOMING_EVENTS:
            widget['data'] = get_upcoming_events(
                db, baby_ids, days_ahead=7
            )
        elif widget_type == WidgetType.CARE_METRICS:
            widget['data'] = get_care_metrics(
                db, baby_ids, widget_timeframe
            )
        # Add other widget types as needed

        dashboard_data['widgets'].append(widget)

    return dashboard_data