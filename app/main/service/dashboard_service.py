from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Type, Union

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.main.model import Growth, Milestone, Pumping
from app.main.model.baby import Baby
from app.main.model.dashboard import DashboardPreference, WidgetType, TimeFrame
from app.main.model.diaper import Diaper
from app.main.model.doctor_visit import DoctorVisit
from app.main.model.feeding import Feeding, FeedingType, BottleContentType
from app.main.model.health import Health
from app.main.model.medication import Medication
from app.main.model.photo import Photo
from app.main.model.sleep import Sleep
from app.main.model.user import User
from app.main.service.baby_service import get_all_babies_for_user


def get_or_create_dashboard_preferences(db: Session, user_id: int) -> Union[DashboardPreference, Type[DashboardPreference]]:
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
        user = db.query(User).filter(User.id == feeding.recorded_by).first()

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
        user = db.query(User).filter(User.id == sleep.recorded_by).first()

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
        user = db.query(User).filter(User.id == diaper.recorded_by).first()

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
        user = db.query(User).filter(User.id == health.recorded_by).first()

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
                'doctor_visit': 0,
                'growth': 0,
                'milestone': 0,
                'photo': 0,
                'pumping': 0
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

    # Count medication
    medications = db.query(Medication).filter(
        Medication.baby_id.in_(baby_ids),
        Medication.time_given.between(start_date, end_date)
    ).all()

    for medication in medications:
        caregiver_id = medication.recorded_by
        metrics['total_activities'] += 1
        metrics['by_activity_type']['medication']['total'] += 1

        if caregiver_id in metrics['by_caregiver']:
            metrics['by_caregiver'][caregiver_id]['total'] += 1
            metrics['by_caregiver'][caregiver_id]['by_activity_type']['medication'] += 1
            metrics['by_activity_type']['medication']['by_caregiver'][caregiver_id] += 1


    # Count doctor visits
    doctor_visits = db.query(DoctorVisit).filter(
        DoctorVisit.baby_id.in_(baby_ids),
        DoctorVisit.visit_date.between(start_date, end_date)
    ).all()

    for doctor_visit in doctor_visits:
        caregiver_id = doctor_visit.recorded_by
        metrics['total_activities'] += 1
        metrics['by_activity_type']['doctor_visit']['total'] += 1

        if caregiver_id in metrics['by_caregiver']:
            metrics['by_caregiver'][caregiver_id]['total'] += 1
            metrics['by_caregiver'][caregiver_id]['by_activity_type']['doctor_visit'] += 1
            metrics['by_activity_type']['doctor_visit']['by_caregiver'][caregiver_id] += 1


    # Count growths
    growths = db.query(Growth).filter(
        Growth.baby_id.in_(baby_ids),
        Growth.measurement_date.between(start_date, end_date)
    ).all()

    for growth in growths:
        caregiver_id = growth.recorded_by
        metrics['total_activities'] += 1
        metrics['by_activity_type']['growth']['total'] += 1

        if caregiver_id in metrics['by_caregiver']:
            metrics['by_caregiver'][caregiver_id]['total'] += 1
            metrics['by_caregiver'][caregiver_id]['by_activity_type']['growth'] += 1
            metrics['by_activity_type']['growth']['by_caregiver'][caregiver_id] += 1

    # Count milestones
    milestones = db.query(Milestone).filter(
        Milestone.baby_id.in_(baby_ids),
        Milestone.achieved_date.between(start_date, end_date)
    ).all()

    for milestone in milestones:
        caregiver_id = milestone.recorded_by
        metrics['total_activities'] += 1
        metrics['by_activity_type']['milestone']['total'] += 1

        if caregiver_id in metrics['by_caregiver']:
            metrics['by_caregiver'][caregiver_id]['total'] += 1
            metrics['by_caregiver'][caregiver_id]['by_activity_type']['milestone'] += 1
            metrics['by_activity_type']['milestone']['by_caregiver'][caregiver_id] += 1

    # Count photos
    photos = db.query(Photo).filter(
        Photo.baby_id.in_(baby_ids),
        Photo.date_taken.between(start_date, end_date)
    ).all()

    for photo in photos:
        caregiver_id = photo.recorded_by
        metrics['total_activities'] += 1
        metrics['by_activity_type']['photo']['total'] += 1

        if caregiver_id in metrics['by_caregiver']:
            metrics['by_caregiver'][caregiver_id]['total'] += 1
            metrics['by_caregiver'][caregiver_id]['by_activity_type']['photo'] += 1
            metrics['by_activity_type']['photo']['by_caregiver'][caregiver_id] += 1


    # Count pumping sessions
    # Note: pumping sessions are user activities, not baby activities
    # So we query for pumping sessions by caregivers who have access to these babies
    pumpings = db.query(Pumping).filter(
        Pumping.user_id.in_(list(caregivers.keys())),
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

    # Calculate percentages
    if metrics['total_activities'] > 0:
        for caregiver_id in metrics['by_caregiver']:
            caregiver_total = metrics['by_caregiver'][caregiver_id]['total']
            metrics['by_caregiver'][caregiver_id]['percentage'] = round(
                (caregiver_total / metrics['total_activities']) * 100, 1
            )

    return metrics


def get_dashboard_data(db: Session, user_id: int, baby_id: Optional[int] = None,
                       timeframe: Optional[str] = None,
                       custom_start: Optional[datetime] = None,
                       custom_end: Optional[datetime] = None) -> Dict[str, Any]:

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


        widget: Dict[str, Union[str, int, None, List[Dict[str, Any]], Dict[str, Any]]] = {
            'type': widget_type,
            'timeframe': widget_timeframe,
            'position': widget_config.get('position', 0),
            'data': None
        }

        # Get widget-specific data with custom dates
        if widget_type == WidgetType.RECENT_ACTIVITIES:
            widget['data'] = get_recent_activities(
                db, baby_ids, widget_timeframe,
                custom_start=custom_start,
                custom_end=custom_end,
                limit=10
            )

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
        elif widget_type == WidgetType.FEEDING_STATS:
            widget['data'] = get_feeding_stats(
                db, baby_ids, widget_timeframe
            )
        elif widget_type == WidgetType.SLEEP_PATTERNS:
            widget['data'] = get_sleep_patterns(
                db, baby_ids, widget_timeframe
            )
        elif widget_type == WidgetType.GROWTH_CHART:
            widget['data'] = get_growth_data(
                db, baby_ids, widget_timeframe
            )
        # Add other widget types as needed

        dashboard_data['widgets'].append(widget)

    return dashboard_data


def get_feeding_stats(db: Session, baby_ids: List[int], timeframe: str,
                      custom_start: Optional[datetime] = None,
                      custom_end: Optional[datetime] = None) -> Dict[str, Any]:
    """Calculate feeding statistics for dashboard widget"""
    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)

    # Initialize stats structure
    stats = {
        'total_feedings': 0,
        'average_per_day': 0,
        'by_type': {
            'breast': 0,
            'bottle': 0,
            'formula': 0,
            'solids': 0,
            'pumping': 0
        },
        'by_content': {
            'breast_milk': 0,
            'formula': 0,
            'mixed': 0,
            'solids': 0
        },
        'average_duration': 0,
        'total_volume': 0,
        'average_volume_per_feeding': 0,
        'daily_trend': [],
        'hourly_distribution': defaultdict(int)  # 0-23 hours
    }

    # Query all feedings in the timeframe
    feedings = db.query(Feeding).filter(
        Feeding.baby_id.in_(baby_ids),
        Feeding.start_time.between(start_date, end_date)
    ).order_by(Feeding.start_time).all()

    if not feedings:
        return stats

    # Process statistics
    total_duration = 0
    duration_count = 0
    total_volume = 0
    volume_count = 0
    daily_counts = defaultdict(int)
    daily_volumes = defaultdict(float)

    for feeding in feedings:
        stats['total_feedings'] += 1

        # Count by feeding type
        if feeding.feeding_type in [FeedingType.BREAST_LEFT, FeedingType.BREAST_RIGHT, FeedingType.BREAST_BOTH]:
            stats['by_type']['breast'] += 1
            stats['by_content']['breast_milk'] += 1
        elif feeding.feeding_type == FeedingType.BOTTLE:
            stats['by_type']['bottle'] += 1
            # Count by bottle content
            if feeding.bottle_content_type == BottleContentType.BREAST_MILK:
                stats['by_content']['breast_milk'] += 1
            elif feeding.bottle_content_type == BottleContentType.FORMULA:
                stats['by_content']['formula'] += 1
            elif feeding.bottle_content_type == BottleContentType.MIXED:
                stats['by_content']['mixed'] += 1
        elif feeding.feeding_type == FeedingType.FORMULA:
            stats['by_type']['formula'] += 1
            stats['by_content']['formula'] += 1
        elif feeding.feeding_type == FeedingType.SOLIDS:
            stats['by_type']['solids'] += 1
            stats['by_content']['solids'] += 1
        elif feeding.feeding_type == FeedingType.PUMPING:
            stats['by_type']['pumping'] += 1

        # Calculate duration
        if feeding.duration:
            total_duration += feeding.duration
            duration_count += 1
        elif feeding.end_time and feeding.start_time:
            # Calculate duration from start and end times
            duration = int((feeding.end_time - feeding.start_time).total_seconds() / 60)
            total_duration += duration
            duration_count += 1

        # Calculate volume
        if feeding.amount:
            total_volume += feeding.amount
            volume_count += 1
            daily_volumes[feeding.start_time.date()] += feeding.amount

        # For pumping sessions, add pumped volumes
        if feeding.feeding_type == FeedingType.PUMPING:
            if feeding.pumped_volume_left:
                total_volume += feeding.pumped_volume_left
                volume_count += 1
                daily_volumes[feeding.start_time.date()] += feeding.pumped_volume_left
            if feeding.pumped_volume_right:
                total_volume += feeding.pumped_volume_right
                volume_count += 1
                daily_volumes[feeding.start_time.date()] += feeding.pumped_volume_right

        # Track daily counts
        daily_counts[feeding.start_time.date()] += 1

        # Track hourly distribution
        hour = feeding.start_time.hour
        stats['hourly_distribution'][hour] += 1

    # Calculate averages
    total_days = max(1, (end_date - start_date).days + 1)
    stats['average_per_day'] = round(stats['total_feedings'] / total_days, 1)

    if duration_count > 0:
        stats['average_duration'] = round(total_duration / duration_count, 1)

    if volume_count > 0:
        stats['total_volume'] = round(total_volume, 1)
        stats['average_volume_per_feeding'] = round(total_volume / volume_count, 1)

    # Create daily trend data
    current_date = start_date.date()
    while current_date <= end_date.date():
        stats['daily_trend'].append({
            'date': current_date.isoformat(),
            'count': daily_counts.get(current_date, 0),
            'volume': round(daily_volumes.get(current_date, 0), 1)
        })
        current_date += timedelta(days=1)

    # Convert hourly distribution to list format for charts
    stats['hourly_distribution'] = [
        {'hour': hour, 'count': stats['hourly_distribution'].get(hour, 0)}
        for hour in range(24)
    ]

    return stats


def get_sleep_patterns(db: Session, baby_ids: List[int], timeframe: str,
                       custom_start: Optional[datetime] = None,
                       custom_end: Optional[datetime] = None) -> Dict[str, Any]:
    """Calculate sleep pattern data for dashboard widget"""
    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)

    patterns = {
        'total_sleep_hours': 0,
        'average_per_day': 0,
        'longest_stretch': 0,
        'shortest_stretch': None,
        'average_stretch': 0,
        'night_vs_day': {
            'night': 0,  # 7pm to 7am
            'day': 0  # 7am to 7pm
        },
        'by_quality': {
            'poor': 0,
            'fair': 0,
            'good': 0,
            'excellent': 0,
            'unknown': 0
        },
        'by_location': defaultdict(int),
        'daily_pattern': [],
        'weekly_average': {  # Average sleep by day of week
            'monday': {'total': 0, 'count': 0},
            'tuesday': {'total': 0, 'count': 0},
            'wednesday': {'total': 0, 'count': 0},
            'thursday': {'total': 0, 'count': 0},
            'friday': {'total': 0, 'count': 0},
            'saturday': {'total': 0, 'count': 0},
            'sunday': {'total': 0, 'count': 0}
        }
    }

    # Query all sleep records in the timeframe
    sleeps = db.query(Sleep).filter(
        Sleep.baby_id.in_(baby_ids),
        Sleep.start_time.between(start_date, end_date)
    ).order_by(Sleep.start_time).all()

    if not sleeps:
        return patterns

    # Process sleep data
    total_minutes = 0
    sleep_durations = []
    daily_sleep = defaultdict(lambda: {'total_minutes': 0, 'count': 0, 'night': 0, 'day': 0})

    for sleep in sleeps:
        # Calculate duration
        duration = 0
        if sleep.duration:
            duration = sleep.duration
        elif sleep.end_time and sleep.start_time:
            duration = int((sleep.end_time - sleep.start_time).total_seconds() / 60)

        if duration > 0:
            total_minutes += duration
            sleep_durations.append(duration)

            # Track longest and shortest stretches
            if duration > patterns['longest_stretch']:
                patterns['longest_stretch'] = duration
            if patterns['shortest_stretch'] is None or duration < patterns['shortest_stretch']:
                patterns['shortest_stretch'] = duration

            # Determine if night or day sleep
            # Night: 7pm (19:00) to 7am (07:00)
            # We'll check the midpoint of sleep to categorize it
            if sleep.end_time:
                midpoint = sleep.start_time + (sleep.end_time - sleep.start_time) / 2
            else:
                midpoint = sleep.start_time + timedelta(minutes=duration / 2)

            hour = midpoint.hour
            if hour >= 19 or hour < 7:  # Night time
                patterns['night_vs_day']['night'] += duration
                daily_sleep[sleep.start_time.date()]['night'] += duration
            else:  # Day time
                patterns['night_vs_day']['day'] += duration
                daily_sleep[sleep.start_time.date()]['day'] += duration

            # Track daily totals
            daily_sleep[sleep.start_time.date()]['total_minutes'] += duration
            daily_sleep[sleep.start_time.date()]['count'] += 1

            # Track weekly patterns
            day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            day_name = day_names[sleep.start_time.weekday()]
            patterns['weekly_average'][day_name]['total'] += duration
            patterns['weekly_average'][day_name]['count'] += 1

        # Track quality
        if sleep.quality:
            patterns['by_quality'][sleep.quality.value] += 1
        else:
            patterns['by_quality']['unknown'] += 1

        # Track location
        if sleep.location:
            patterns['by_location'][sleep.location.value] += 1
        else:
            patterns['by_location']['unknown'] += 1

    # Calculate averages
    patterns['total_sleep_hours'] = round(total_minutes / 60, 1)

    total_days = max(1, (end_date - start_date).days + 1)
    patterns['average_per_day'] = round(patterns['total_sleep_hours'] / total_days, 1)

    if sleep_durations:
        patterns['average_stretch'] = round(sum(sleep_durations) / len(sleep_durations), 0)

    # Convert night/day from minutes to hours
    patterns['night_vs_day']['night'] = round(patterns['night_vs_day']['night'] / 60, 1)
    patterns['night_vs_day']['day'] = round(patterns['night_vs_day']['day'] / 60, 1)

    # Create daily pattern data
    current_date = start_date.date()
    while current_date <= end_date.date():
        daily_data = daily_sleep.get(current_date, {'total_minutes': 0, 'count': 0, 'night': 0, 'day': 0})
        patterns['daily_pattern'].append({
            'date': current_date.isoformat(),
            'total_hours': round(daily_data['total_minutes'] / 60, 1),
            'count': daily_data['count'],
            'night_hours': round(daily_data['night'] / 60, 1),
            'day_hours': round(daily_data['day'] / 60, 1)
        })
        current_date += timedelta(days=1)

    # Calculate weekly averages
    for day_name, data in patterns['weekly_average'].items():
        if data['count'] > 0:
            patterns['weekly_average'][day_name] = round(data['total'] / data['count'] / 60, 1)
        else:
            patterns['weekly_average'][day_name] = 0

    # Convert location dict to list for charts
    patterns['by_location'] = [
        {'location': location, 'count': count}
        for location, count in patterns['by_location'].items()
    ]

    # Convert durations from minutes to hours for display
    patterns['longest_stretch'] = round(patterns['longest_stretch'] / 60, 1)
    if patterns['shortest_stretch'] is not None:
        patterns['shortest_stretch'] = round(patterns['shortest_stretch'] / 60, 1)
    patterns['average_stretch'] = round(patterns['average_stretch'] / 60, 1)

    return patterns


def get_growth_data(db: Session, baby_ids: List[int], timeframe: str,
                    custom_start: Optional[datetime] = None,
                    custom_end: Optional[datetime] = None) -> Dict[str, Any]:
    """Calculate growth data for dashboard widget"""
    start_date, end_date = get_timeframe_dates(timeframe, custom_start, custom_end)

    growth_data = {
        'latest_measurements': {
            'weight': None,
            'height': None,
            'measurement_date': None
        },
        'growth_trends': {
            'weight_change': 0,  # change in kg over timeframe
            'height_change': 0,  # change in cm over timeframe
            'weight_trend': 'stable',  # 'increasing', 'decreasing', 'stable'
            'height_trend': 'stable'
        },
        'measurement_counts': {
            'total_measurements': 0,
            'weight_measurements': 0,
            'height_measurements': 0
        },
        'timeline_data': []  # For charting - list of measurements over time
    }

    # Query growth measurements within timeframe
    growth_records = db.query(Growth).filter(
        Growth.baby_id.in_(baby_ids),
        Growth.measurement_date.between(start_date, end_date)
    ).order_by(Growth.measurement_date.asc()).all()

    if not growth_records:
        return growth_data

    # Calculate basic counts
    growth_data['measurement_counts']['total_measurements'] = len(growth_records)
    growth_data['measurement_counts']['weight_measurements'] = sum(
        1 for record in growth_records if record.weight is not None
    )
    growth_data['measurement_counts']['height_measurements'] = sum(
        1 for record in growth_records if record.height is not None
    )

    # Get latest measurements
    latest_record = growth_records[-1]  # Records are ordered by date
    growth_data['latest_measurements'] = {
        'weight': latest_record.weight,
        'height': latest_record.height,
        'measurement_date': latest_record.measurement_date
    }

    # Calculate growth trends if we have multiple measurements
    if len(growth_records) > 1:
        first_record = growth_records[0]

        # Weight trend calculation
        if first_record.weight and latest_record.weight:
            weight_change = latest_record.weight - first_record.weight
            growth_data['growth_trends']['weight_change'] = round(weight_change, 2)

            if weight_change > 0.1:  # More than 100g gain
                growth_data['growth_trends']['weight_trend'] = 'increasing'
            elif weight_change < -0.1:  # More than 100g loss
                growth_data['growth_trends']['weight_trend'] = 'decreasing'
            else:
                growth_data['growth_trends']['weight_trend'] = 'stable'

        # Height trend calculation
        if first_record.height and latest_record.height:
            height_change = latest_record.height - first_record.height
            growth_data['growth_trends']['height_change'] = round(height_change, 1)

            if height_change > 0.5:  # More than 0.5cm growth
                growth_data['growth_trends']['height_trend'] = 'increasing'
            elif height_change < -0.5:  # Unlikely but checking for data errors
                growth_data['growth_trends']['height_trend'] = 'decreasing'
            else:
                growth_data['growth_trends']['height_trend'] = 'stable'

    # Prepare timeline data for charting
    for record in growth_records:
        timeline_entry = {
            'date': record.measurement_date.isoformat(),
            'weight': record.weight,
            'height': record.height,
            'notes': record.notes
        }
        growth_data['timeline_data'].append(timeline_entry)

    return growth_data
