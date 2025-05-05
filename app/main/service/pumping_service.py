from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Union, Any

from sqlalchemy.orm import Session

from app.main.model.pumping import Pumping
from app.main.service.baby_service import get_baby_if_authorized


def create_pumping_session(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Pumping, Dict[str, str]]:
    """Create a new pumping session record"""
    # Check if user is authorized to add pumping sessions for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Calculate duration if both start and end times are provided
    duration = data.get('duration')
    if data.get('end_time') and not duration:
        # Calculate duration in minutes
        delta = data['end_time'] - data['start_time']
        duration = int(delta.total_seconds() / 60)

    # Create new pumping session
    new_session = Pumping(
        created_at=datetime.utcnow(),
        start_time=data['start_time'],
        end_time=data.get('end_time'),
        duration=duration,
        volume_left=data.get('volume_left'),
        volume_right=data.get('volume_right'),
        notes=data.get('notes'),
        baby_id=data['baby_id']
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


def get_pumping_summary(db: Session, baby_id: int, current_user_id: int, days: int = 7) -> Union[
    Dict[str, Any], Dict[str, str]]:
    """Get pumping statistics for a period of days"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Calculate the start date
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get all pumping sessions in the period
    sessions = db.query(Pumping).filter(
        Pumping.baby_id == baby_id,
        Pumping.start_time >= start_date
    ).order_by(Pumping.start_time).all()

    # Initialize data structures
    daily_volume = defaultdict(float)
    side_totals = {'left': 0, 'right': 0}
    total_duration = 0

    # Analyze data
    for session in sessions:
        date_str = session.start_time.strftime('%Y-%m-%d')

        # Sum volumes
        left_vol = session.volume_left or 0
        right_vol = session.volume_right or 0
        session_total = left_vol + right_vol

        daily_volume[date_str] += session_total
        side_totals['left'] += left_vol
        side_totals['right'] += right_vol

        # Add duration
        if session.duration:
            total_duration += session.duration

    # Calculate averages
    num_days = len(daily_volume) or 1  # Avoid division by zero
    avg_daily_volume = sum(daily_volume.values()) / num_days
    avg_session_volume = sum(daily_volume.values()) / len(sessions) if sessions else 0

    # Prepare the response
    summary = {
        'total_sessions': len(sessions),
        'total_volume_ml': sum(daily_volume.values()),
        'avg_daily_volume_ml': round(avg_daily_volume, 1),
        'avg_session_volume_ml': round(avg_session_volume, 1),
        'side_comparison': {
            'left_ml': side_totals['left'],
            'right_ml': side_totals['right'],
            'difference_ml': abs(side_totals['left'] - side_totals['right']),
            'dominant_side': 'left' if side_totals['left'] > side_totals['right'] else 'right'
        },
        'total_duration_minutes': total_duration,
        'avg_duration_minutes': round(total_duration / len(sessions), 1) if sessions else 0,
        'daily_volumes': [{'date': k, 'volume_ml': v} for k, v in sorted(daily_volume.items())]
    }

    return {
        'status': 'success',
        'summary': summary
    }