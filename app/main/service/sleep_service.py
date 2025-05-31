from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Union, Any, Optional, Type, List

from sqlalchemy.orm import Session

from app.main.model import User
from app.main.model.sleep import Sleep
from app.main.service.baby_service import get_baby_if_authorized


def create_sleep(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Sleep, Dict[str, str]]:
    """Create a new sleep record for a baby"""
    # Check if user is authorized to add sleep records for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Calculate duration if both start and end times are provided
    duration = data.get('duration')
    if data.get('end_time') and not duration:
        # Calculate duration in minutes
        delta = data['end_time'] - data['start_time']
        duration = int(delta.total_seconds() / 60)

    # Create new sleep record
    new_sleep = Sleep(
        created_at=datetime.utcnow(),
        start_time=data['start_time'],
        end_time=data.get('end_time'),
        duration=duration,
        quality=data.get('quality'),
        location=data.get('location'),
        training_method=data.get('training_method'),
        notes=data.get('notes'),
        baby_id=data['baby_id'],
        recorded_by=current_user_id
    )

    db.add(new_sleep)
    db.commit()
    db.refresh(new_sleep)

    caregiver = db.query(User).filter(User.id == new_sleep.recorded_by).first()
    if caregiver:
        new_sleep.caregiver_name = caregiver.name
    return new_sleep


def get_sleeps_for_baby(db: Session, baby_id: int, current_user_id: int, 
                       skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None, 
                       end_date: Optional[datetime] = None) -> Union[dict[str, str], list[Type[Sleep]]]:
    """Get sleep records for a baby with optional date filtering"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query sleeps
    query = db.query(Sleep).filter(Sleep.baby_id == baby_id)
    
    # Apply date filters if provided
    if start_date:
        query = query.filter(Sleep.start_time >= start_date)
    if end_date:
        query = query.filter(Sleep.start_time <= end_date)
    
    # Order by time descending (newest first)
    query = query.order_by(Sleep.start_time.desc())
    
    # Apply pagination
    sleeps = query.offset(skip).limit(limit).all()

    # Add caregiver information to each feeding record
    for sleep in sleeps:
        caregiver = db.query(User).filter(User.id == sleep.recorded_by).first()
        if caregiver:
            sleep.caregiver_name = caregiver.name
    
    return sleeps


def get_sleep(db: Session, sleep_id: int, current_user_id: int) -> Union[dict[str, str], dict[str, str], Type[Sleep]]:
    """Get a specific sleep record by ID"""
    # Get the sleep record
    sleep = db.query(Sleep).filter(Sleep.id == sleep_id).first()
    
    if not sleep:
        return {
            'status': 'fail',
            'message': 'Sleep record not found',
        }
    
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, sleep.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    caregiver = db.query(User).filter(User.id == sleep.recorded_by).first()
    if caregiver:
        sleep.caregiver_name = caregiver.name
    
    return sleep


def update_sleep(db: Session, sleep_id: int, data: Dict[str, Any], current_user_id: int) -> Union[
    dict[str, str], dict[str, str], Type[Sleep]]:
    """Update a sleep record"""
    # Get the sleep record
    sleep = db.query(Sleep).filter(Sleep.id == sleep_id).first()
    
    if not sleep:
        return {
            'status': 'fail',
            'message': 'Sleep record not found',
        }
    
    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, sleep.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby
    
    # Calculate duration if end_time is updated
    start_time = data.get('start_time', sleep.start_time)
    end_time = data.get('end_time')
    duration = data.get('duration')
    
    if end_time and not duration:
        # Calculate duration in minutes
        delta = end_time - start_time
        duration = int(delta.total_seconds() / 60)
    
    # Update sleep record
    sleep.start_time = start_time
    if end_time:
        sleep.end_time = end_time
    if duration:
        sleep.duration = duration
    sleep.quality = data.get('quality', sleep.quality)
    sleep.notes = data.get('notes', sleep.notes)
    sleep.location = data.get('location', sleep.location)
    sleep.training_method = data.get('training_method', sleep.training_method)

    
    db.commit()
    db.refresh(sleep)
    return sleep


def delete_sleep(db: Session, sleep_id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a sleep record"""
    # Get the sleep record
    sleep = db.query(Sleep).filter(Sleep.id == sleep_id).first()
    
    if not sleep:
        return {
            'status': 'fail',
            'message': 'Sleep record not found',
        }
    
    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, sleep.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby
    
    # Delete the sleep record
    db.delete(sleep)
    db.commit()
    return {'status': 'DELETED'}


def get_sleep_patterns(db: Session, baby_id: int, current_user_id: int, days: int = 7) -> Union[
    Dict[str, Any], Dict[str, str]]:
    """Get sleep patterns for a specified number of days"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Calculate the start date based on the number of days
    end_date = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
    start_date = (end_date - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Get all sleep records for the baby in the specified period
    sleeps = db.query(Sleep).filter(
        Sleep.baby_id == baby_id,
        Sleep.start_time >= start_date,
        Sleep.start_time <= end_date
    ).order_by(Sleep.start_time).all()

    # Initialize data structures for analysis
    daily_sleep = defaultdict(int)  # Total minutes per day
    daily_naps = defaultdict(int)  # Number of naps per day
    daily_nap_duration = defaultdict(int)  # Total nap duration per day
    night_sleep = defaultdict(int)  # Night sleep duration per day
    sleep_locations = defaultdict(int)  # Count by location
    sleep_qualities = []  # Store all quality ratings for averaging

    # Analyze sleep data
    for sleep in sleeps:
        # Get date string for daily grouping
        date_str = sleep.start_time.strftime('%Y-%m-%d')

        # Add to total sleep time if duration is available
        if sleep.duration:
            daily_sleep[date_str] += sleep.duration

            # Count as night sleep if between 7pm and 7am
            hour = sleep.start_time.hour
            if hour >= 19 or hour < 7:  # Changed <= to < for clarity
                night_sleep[date_str] += sleep.duration
            else:
                # It's a nap
                daily_naps[date_str] += 1
                daily_nap_duration[date_str] += sleep.duration

        # Track sleep locations using proper enum handling
        if sleep.location:
            location_value = sleep.location.value if hasattr(sleep.location, 'value') else str(sleep.location)
            sleep_locations[location_value] += 1

        # Track sleep quality for scoring
        if sleep.quality:
            quality_value = sleep.quality.value if hasattr(sleep.quality, 'value') else str(sleep.quality)
            sleep_qualities.append(quality_value)

    # Calculate totals
    total_sleep_minutes = sum(daily_sleep.values())
    total_night_sleep_minutes = sum(night_sleep.values())
    total_nap_minutes = sum(daily_nap_duration.values())
    total_naps = sum(daily_naps.values())

    # Average per day over the ENTIRE analysis period
    avg_total_sleep = total_sleep_minutes / days
    avg_night_sleep = total_night_sleep_minutes / days
    avg_nap_duration = total_nap_minutes / days if days > 0 else 0
    avg_naps = total_naps / days

    # Calculate sleep quality score with days_with_data info
    days_with_data = len(daily_sleep)
    quality_score, quality_rating = calculate_sleep_quality_score(
        avg_total_sleep, sleep_qualities, days, days_with_data
    )

    # Prepare the response
    patterns = {
        'summary': {
            'avg_total_sleep_minutes': round(avg_total_sleep, 1),
            'avg_total_sleep_hours': round(avg_total_sleep / 60, 2),
            'avg_night_sleep_minutes': round(avg_night_sleep, 1),
            'avg_night_sleep_hours': round(avg_night_sleep / 60, 2),
            'avg_nap_duration_minutes': round(avg_nap_duration, 1),
            'avg_nap_duration_hours': round(avg_nap_duration / 60, 2),
            'avg_naps_per_day': round(avg_naps, 2),
            'sleep_quality_score': quality_score,
            'sleep_quality_rating': quality_rating,
            'total_days_analyzed': days,
            'days_with_sleep_data': days_with_data
        },
        'by_location': dict(sleep_locations),
        'daily_sleep': [
            {
                'date': k,
                'total_minutes': v,
                'total_hours': round(v / 60, 2),
                'night_minutes': night_sleep.get(k, 0),
                'nap_minutes': daily_nap_duration.get(k, 0),
                'nap_count': daily_naps.get(k, 0)
            }
            for k, v in sorted(daily_sleep.items())
        ]

    }

    return {
        'status': 'success',
        'patterns': patterns
    }


def calculate_sleep_quality_score(avg_daily_minutes: float, qualities: List[str],
                                 days: int, days_with_data: int) -> tuple[int, str]:
    """
    Calculate sleep quality score based on average daily sleep and recorded quality ratings.

    Baby sleep recommendations (approximate):
    - Newborns (0-3 months): 14-17 hours per day
    - Infants (4-11 months): 12-15 hours per day
    - Toddlers (1-2 years): 11-14 hours per day
    """

    # Handle case where there's no sleep data in the period
    if days_with_data == 0:
        # No data available - return a neutral "No Data" result
        return 0, "No Data"

    # Convert to hours for easier calculation
    avg_daily_hours = avg_daily_minutes / 60

    # Base score on sleep duration (assuming infant range as default)
    if avg_daily_hours >= 12:
        duration_score = 100
    elif avg_daily_hours >= 10:
        duration_score = 80
    elif avg_daily_hours >= 8:
        duration_score = 60
    elif avg_daily_hours >= 6:
        duration_score = 40
    elif avg_daily_hours >= 3:
        duration_score = 20
    else:
        duration_score = 10  # Very poor sleep

    # Factor in recorded quality ratings if available
    quality_score = 50  # Default neutral score
    if qualities:
        quality_mapping = {
            'excellent': 100,
            'good': 80,
            'fair': 60,
            'poor': 30
        }
        quality_scores = [quality_mapping.get(q.lower(), 50) for q in qualities]
        quality_score = sum(quality_scores) / len(quality_scores)

    # Combine duration and quality scores (70% duration, 30% quality)
    final_score = int((duration_score * 0.7) + (quality_score * 0.3))

    # Determine rating
    if final_score >= 80:
        rating = "Excellent"
    elif final_score >= 65:
        rating = "Good"
    elif final_score >= 45:
        rating = "Fair"
    else:
        rating = "Poor"

    return final_score, rating
