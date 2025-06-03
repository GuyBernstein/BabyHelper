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


def get_sleep_patterns(db: Session, baby_id: int, current_user_id: int, days: int = 7,
                       calculation_method: str = None) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Get sleep patterns for a specified number of days

    Args:
        db: Database session
        baby_id: ID of the baby
        current_user_id: ID of the current user
        days: Number of days to analyze (default: 7)
        calculation_method: Sleep quality calculation method - "PSQI" or "custom" (default: None)
                          If None, no quality calculation is performed
    """
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
            if hour >= 19 or hour < 7:
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

    # Calculate days with data
    days_with_data = len(daily_sleep)

    # Calculate baby's age in months if birth date is available
    baby_age_months = None
    if hasattr(baby, 'birthdate') and baby.birthdate:
        age_delta = datetime.utcnow() - baby.birthdate
        baby_age_months = age_delta.days // 30  # Approximate months

    # Prepare base summary
    summary = {
        'avg_total_sleep_minutes': round(avg_total_sleep, 1),
        'avg_total_sleep_hours': round(avg_total_sleep / 60, 2),
        'avg_night_sleep_minutes': round(avg_night_sleep, 1),
        'avg_night_sleep_hours': round(avg_night_sleep / 60, 2),
        'avg_nap_duration_minutes': round(avg_nap_duration, 1),
        'avg_nap_duration_hours': round(avg_nap_duration / 60, 2),
        'avg_naps_per_day': round(avg_naps, 2),
        'total_days_analyzed': days,
        'days_with_sleep_data': days_with_data
    }

    # Calculate sleep quality only if method is specified
    if calculation_method in ["PSQI", "custom"]:
        if days_with_data == 0:
            # Handle no data case
            summary['sleep_quality_score'] = 0
            summary['sleep_quality_rating'] = "No Data"
            summary['sleep_quality_explanation'] = "No sleep data available for the selected period"
            summary['calculation_method'] = calculation_method
        else:
            # Prepare sleep_data dictionary for the calculation functions
            sleep_data = {
                'avg_total_sleep_minutes': avg_total_sleep,
                'avg_night_sleep_minutes': avg_night_sleep,
                'avg_naps_per_day': avg_naps,
                'avg_nap_duration_minutes': avg_nap_duration,
                'sleep_qualities': sleep_qualities,
                'days_with_data': days_with_data,
                'days': days,
                'sleep_locations': dict(sleep_locations),
                'baby_age_months': baby_age_months
            }

            # Calculate sleep quality score using the specified method
            quality_score, quality_rating, quality_explanation = calculate_sleep_quality(
                sleep_data, calculation_method
            )

            summary['sleep_quality_score'] = quality_score
            summary['sleep_quality_rating'] = quality_rating
            summary['sleep_quality_explanation'] = quality_explanation
            summary['calculation_method'] = calculation_method

    # Prepare the response
    patterns = {
        'summary': summary,
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


def calculate_sleep_quality(sleep_data, calculation_method):
    """
    Calculate sleep quality metrics for babies based on sleep data and specified method.
    Args:
    sleep_data (dict): Dictionary containing sleep metrics
    calculation_method (str): Either "PSQI" or "custom"

    Returns:
        tuple: (score, rating, explanation)
    """
    if calculation_method == "PSQI":
        return calculate_psqi_score(sleep_data)
    elif calculation_method == "custom":
        return calculate_custom_score(sleep_data)
    else:
        return 0, "Unknown", "Invalid calculation method specified"


def calculate_psqi_score(sleep_data):
    """Calculate PSQI-Inspired Baby Sleep Score (0-100 scale)"""
    # Extract data
    avg_total_sleep_minutes = sleep_data.get('avg_total_sleep_minutes', 0)
    avg_night_sleep_minutes = sleep_data.get('avg_night_sleep_minutes', 0)
    avg_naps_per_day = sleep_data.get('avg_naps_per_day', 0)
    sleep_qualities = sleep_data.get('sleep_qualities', [])
    days_with_data = sleep_data.get('days_with_data', 0)
    days = sleep_data.get('days', 1)
    baby_age_months = sleep_data.get('baby_age_months', None)

    # Convert to hours
    avg_total_sleep_hours = avg_total_sleep_minutes / 60

    # Component calculations
    components = {}

    # 1. Sleep Duration Component (25%)
    # Determine age-appropriate sleep targets
    if baby_age_months is not None:
        if baby_age_months <= 3:
            # Newborns (0-3 months): 14-17 hours
            target_min, target_max, target_midpoint = 14, 17, 15.5
            ideal_naps_min, ideal_naps_max = 3, 5  # Multiple short naps
        elif baby_age_months <= 11:
            # Infants (4-11 months): 12-15 hours
            target_min, target_max, target_midpoint = 12, 15, 13.5
            ideal_naps_min, ideal_naps_max = 2, 3
        elif baby_age_months <= 24:
            # Toddlers (1-2 years): 11-14 hours
            target_min, target_max, target_midpoint = 11, 14, 12.5
            ideal_naps_min, ideal_naps_max = 1, 2
        else:
            # Older toddlers (2+ years): 10-13 hours
            target_min, target_max, target_midpoint = 10, 13, 11.5
            ideal_naps_min, ideal_naps_max = 0, 1
    else:
        # Default to infant range if age unknown
        target_min, target_max, target_midpoint = 12, 15, 13.5
        ideal_naps_min, ideal_naps_max = 2, 3

    # Calculate duration score based on age-appropriate range
    if target_min <= avg_total_sleep_hours <= target_max:
        duration_score = 100
    elif avg_total_sleep_hours < target_min:
        # Score decreases as sleep gets further below minimum
        deficit = target_min - avg_total_sleep_hours
        duration_score = max(0, 100 - (deficit * 15))  # Lose 15 points per hour below minimum
    else:
        # Score decreases as sleep gets further above maximum
        excess = avg_total_sleep_hours - target_max
        duration_score = max(0, 100 - (excess * 10))  # Lose 10 points per hour above maximum

    components['duration'] = duration_score * 0.25

    # 2. Sleep Quality Component (20%)
    quality_map = {'Excellent': 100, 'Good': 75, 'Fair': 50, 'Poor': 25}
    if sleep_qualities:
        quality_scores = [quality_map.get(q, 50) for q in sleep_qualities]
        quality_score = sum(quality_scores) / len(quality_scores)
    else:
        quality_score = 50  # Default when no data
    components['quality'] = quality_score * 0.20

    # 3. Sleep Efficiency Component (20%)
    efficiency_score = (days_with_data / days * 100) if days > 0 else 0
    components['efficiency'] = efficiency_score * 0.20

    # 4. Sleep Pattern Component (20%)
    if avg_total_sleep_minutes > 0:
        night_day_ratio = avg_night_sleep_minutes / avg_total_sleep_minutes
    else:
        night_day_ratio = 0

    # Age-adjusted pattern scoring
    if baby_age_months is not None and baby_age_months <= 3:
        # Newborns have less consolidated night sleep
        if night_day_ratio >= 0.5:
            pattern_score = 100
        elif 0.4 <= night_day_ratio < 0.5:
            pattern_score = 75
        elif 0.3 <= night_day_ratio < 0.4:
            pattern_score = 50
        else:
            pattern_score = 25
    else:
        # Older babies should have more consolidated night sleep
        if night_day_ratio >= 0.7:
            pattern_score = 100
        elif 0.5 <= night_day_ratio < 0.7:
            pattern_score = 75
        elif 0.3 <= night_day_ratio < 0.5:
            pattern_score = 50
        else:
            pattern_score = 25
    components['pattern'] = pattern_score * 0.20

    # 5. Nap Consistency Component (15%)
    if ideal_naps_min <= avg_naps_per_day <= ideal_naps_max:
        nap_score = 100
    else:
        deviation = min(abs(avg_naps_per_day - ideal_naps_min),
                        abs(avg_naps_per_day - ideal_naps_max))
        nap_score = max(0, 100 - (deviation * 25))
    components['nap_consistency'] = nap_score * 0.15

    # Calculate final score
    final_score = sum(components.values())

    # Determine rating
    if final_score >= 85:
        rating = "Excellent"
    elif final_score >= 70:
        rating = "Good"
    elif final_score >= 50:
        rating = "Fair"
    else:
        rating = "Poor"

    # Create explanation with age context
    age_context = ""
    if baby_age_months is not None:
        if baby_age_months <= 3:
            age_context = " (Newborn: 0-3 months)"
        elif baby_age_months <= 11:
            age_context = " (Infant: 4-11 months)"
        elif baby_age_months <= 24:
            age_context = " (Toddler: 1-2 years)"
        else:
            age_context = " (Toddler: 2+ years)"

    explanation = (f"PSQI-Inspired Score: {final_score:.1f}/100 {age_context}. "
                   f"Components - Duration: {duration_score:.0f}%, "
                   f"Quality: {quality_score:.0f}%, "
                   f"Efficiency: {efficiency_score:.0f}%, "
                   f"Sleep Pattern: {pattern_score:.0f}%, "
                   f"Nap Consistency: {nap_score:.0f}%")

    return final_score, rating, explanation


def calculate_custom_score(sleep_data):
    """Calculate custom sleep score based on multiple factors"""
    # Extract data
    avg_total_sleep_minutes = sleep_data.get('avg_total_sleep_minutes', 0)
    avg_night_sleep_minutes = sleep_data.get('avg_night_sleep_minutes', 0)
    sleep_qualities = sleep_data.get('sleep_qualities', [])
    days_with_data = sleep_data.get('days_with_data', 0)
    days = sleep_data.get('days', 1)
    sleep_locations = sleep_data.get('sleep_locations', {})
    baby_age_months = sleep_data.get('baby_age_months', None)

    score_components = []

    # Total sleep duration (0-35 points) - age adjusted
    avg_total_sleep_hours = avg_total_sleep_minutes / 60

    if baby_age_months is not None:
        if baby_age_months <= 3:
            # Newborns need more sleep
            if avg_total_sleep_hours >= 15:
                duration_points = 35
            elif avg_total_sleep_hours >= 14:
                duration_points = 30
            elif avg_total_sleep_hours >= 12:
                duration_points = 20
            else:
                duration_points = max(0, avg_total_sleep_hours * 2.5)
        elif baby_age_months <= 11:
            # Infants
            if avg_total_sleep_hours >= 13:
                duration_points = 35
            elif avg_total_sleep_hours >= 12:
                duration_points = 30
            elif avg_total_sleep_hours >= 10:
                duration_points = 20
            else:
                duration_points = max(0, avg_total_sleep_hours * 2)
        elif baby_age_months <= 24:
            # Toddlers
            if avg_total_sleep_hours >= 12:
                duration_points = 35
            elif avg_total_sleep_hours >= 11:
                duration_points = 30
            elif avg_total_sleep_hours >= 9:
                duration_points = 20
            else:
                duration_points = max(0, avg_total_sleep_hours * 2)
        else:
            # Older toddlers
            if avg_total_sleep_hours >= 11:
                duration_points = 35
            elif avg_total_sleep_hours >= 10:
                duration_points = 30
            elif avg_total_sleep_hours >= 8:
                duration_points = 20
            else:
                duration_points = max(0, avg_total_sleep_hours * 2)
    else:
        # Default scoring when age is unknown
        if avg_total_sleep_hours >= 14:
            duration_points = 35
        elif avg_total_sleep_hours >= 12:
            duration_points = 30
        elif avg_total_sleep_hours >= 10:
            duration_points = 20
        else:
            duration_points = max(0, avg_total_sleep_hours * 2)

    score_components.append(duration_points)

    # Night sleep proportion (0-25 points) - age adjusted
    if avg_total_sleep_minutes > 0:
        night_proportion = avg_night_sleep_minutes / avg_total_sleep_minutes
        if baby_age_months is not None and baby_age_months <= 3:
            # Newborns have less consolidated night sleep, so be more lenient
            night_points = min(25, night_proportion * 35)
        else:
            night_points = night_proportion * 25
    else:
        night_points = 0
    score_components.append(night_points)

    # Data consistency (0-20 points)
    consistency_ratio = days_with_data / days if days > 0 else 0
    consistency_points = consistency_ratio * 20
    score_components.append(consistency_points)

    # Sleep quality ratings (0-15 points)
    quality_map = {'Excellent': 15, 'Good': 11, 'Fair': 7, 'Poor': 3}
    if sleep_qualities:
        quality_scores = [quality_map.get(q, 7) for q in sleep_qualities]
        quality_points = sum(quality_scores) / len(quality_scores)
    else:
        quality_points = 7  # Default to fair
    score_components.append(quality_points)

    # Sleep location consistency (0-5 points)
    if sleep_locations:
        total_locations = sum(sleep_locations.values())
        if total_locations > 0:
            max_location_count = max(sleep_locations.values())
            location_consistency = max_location_count / total_locations
            location_points = location_consistency * 5
        else:
            location_points = 2.5
    else:
        location_points = 2.5  # Default
    score_components.append(location_points)

    # Calculate final score
    final_score = sum(score_components)

    # Determine rating
    if final_score >= 85:
        rating = "Excellent"
    elif final_score >= 70:
        rating = "Good"
    elif final_score >= 50:
        rating = "Fair"
    else:
        rating = "Poor"

    # Add age context to explanation
    age_context = ""
    if baby_age_months is not None:
        age_context = f" (Age: {baby_age_months} months)"

    explanation = (f"Custom Score: {final_score:.1f}/100 {age_context}. "
                   f"Based on sleep duration ({duration_points:.0f} pts), "
                   f"night sleep ratio ({night_points:.0f} pts), "
                   f"data consistency ({consistency_points:.0f} pts), "
                   f"sleep quality ({quality_points:.0f} pts), "
                   f"and location consistency ({location_points:.0f} pts)")

    return final_score, rating, explanation