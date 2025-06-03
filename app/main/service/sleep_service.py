from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Union, Any, Optional, Type, List, Tuple

from sqlalchemy.orm import Session

from app.main.model import User
from app.main.model.sleep import Sleep
from app.main.service.baby_service import get_baby_if_authorized

# Age-based sleep requirements configuration
SLEEP_REQUIREMENTS = {
    'newborn': {  # 0-3 months
        'age_range': (0, 3),
        'sleep_range': (14, 17),
        'sleep_midpoint': 15.5,
        'nap_range': (3, 5),
        'min_night_ratio': 0.4,
        'name': 'Newborn: 0-3 months'
    },
    'infant': {  # 4-11 months
        'age_range': (4, 11),
        'sleep_range': (12, 15),
        'sleep_midpoint': 13.5,
        'nap_range': (2, 3),
        'min_night_ratio': 0.6,
        'name': 'Infant: 4-11 months'
    },
    'young_toddler': {  # 12-24 months
        'age_range': (12, 24),
        'sleep_range': (11, 14),
        'sleep_midpoint': 12.5,
        'nap_range': (1, 2),
        'min_night_ratio': 0.7,
        'name': 'Toddler: 1-2 years'
    },
    'older_toddler': {  # 24+ months
        'age_range': (25, float('inf')),
        'sleep_range': (10, 13),
        'sleep_midpoint': 11.5,
        'nap_range': (0, 1),
        'min_night_ratio': 0.7,
        'name': 'Toddler: 2+ years'
    }
}

# Quality scoring mappings
QUALITY_SCORES = {
    'Excellent': 100,
    'Good': 75,
    'Fair': 50,
    'Poor': 25
}

# Constants
MIN_ACCEPTABLE_SLEEP_HOURS = 6  # Below this is critically low
NIGHT_SLEEP_START_HOUR = 19  # 7 PM
NIGHT_SLEEP_END_HOUR = 7  # 7 AM
DEFAULT_AGE_CATEGORY = 'infant'
DEFAULT_QUALITY_SCORE = 50
MONTHS_PER_YEAR = 30  # Approximate days per month for age calculation

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


"""
Sleep Pattern Analysis

This pattern analysis provides comprehensive sleep pattern analysis for babies/toddlers,
including age-appropriate sleep recommendations and quality scoring using both
PSQI-inspired and custom methodologies.
"""
def get_sleep_patterns(
        db: Session,
        baby_id: int,
        current_user_id: int,
        days: int = 7,
        calculation_method: Optional[str] = None
) -> Union[Dict[str, Any], Dict[str, str]]:
    """
    Analyze sleep patterns for a baby over a specified period.

    Args:
        db: Database session
        baby_id: ID of the baby
        current_user_id: ID of the current user
        days: Number of days to analyze (default: 7)
        calculation_method: Quality calculation method - "PSQI" or "custom" (optional)

    Returns:
        Dictionary containing sleep patterns analysis and quality scores
    """
    # Verify authorization
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Define analysis period
    end_date = _get_end_of_day(datetime.utcnow())
    start_date = _get_start_of_day(end_date - timedelta(days=days - 1))

    # Retrieve sleep records
    sleep_records = _fetch_sleep_records(db, baby_id, start_date, end_date)

    # Analyze sleep data
    sleep_analysis = _analyze_sleep_records(sleep_records)

    # Calculate baby's age
    baby_age_months = _calculate_age_months(baby.birthdate) if hasattr(baby, 'birthdate') and baby.birthdate else None

    # Generate summary statistics
    summary = _create_sleep_summary(sleep_analysis, days, baby_age_months)

    # Add quality assessment if requested
    if calculation_method in ["PSQI", "custom"]:
        quality_data = _calculate_sleep_quality(
            sleep_analysis,
            summary,
            baby_age_months,
            calculation_method
        )
        summary.update(quality_data)

    return {
        'status': 'success',
        'patterns': {
            'summary': summary,
            'by_location': dict(sleep_analysis['locations']),
            'daily_sleep': _format_daily_sleep(sleep_analysis)
        }
    }


def _get_start_of_day(date: datetime) -> datetime:
    """Return the start of the given day (00:00:00.000)."""
    return date.replace(hour=0, minute=0, second=0, microsecond=0)


def _get_end_of_day(date: datetime) -> datetime:
    """Return the end of the given day (23:59:59.999)."""
    return date.replace(hour=23, minute=59, second=59, microsecond=999999)


def _fetch_sleep_records(db: Session, baby_id: int, start_date: datetime, end_date: datetime) -> List:
    """Fetch sleep records within the specified date range."""
    return db.query(Sleep).filter(
        Sleep.baby_id == baby_id,
        Sleep.start_time >= start_date,
        Sleep.start_time <= end_date
    ).order_by(Sleep.start_time).all()


def _is_night_sleep(hour: int) -> bool:
    """Determine if the given hour falls within night sleep time (7pm-7am)."""
    return hour >= NIGHT_SLEEP_START_HOUR or hour < NIGHT_SLEEP_END_HOUR


def _analyze_sleep_records(sleep_records: List) -> Dict[str, Any]:
    """
    Analyze sleep records and aggregate data by various dimensions.

    Returns:
        Dictionary containing aggregated sleep data by date, location, and quality
    """
    analysis = {
        'daily_total': defaultdict(int),
        'daily_naps': defaultdict(int),
        'daily_nap_duration': defaultdict(int),
        'daily_night': defaultdict(int),
        'locations': defaultdict(int),
        'qualities': []
    }

    for sleep in sleep_records:
        if not sleep.duration:
            continue

        date_str = sleep.start_time.strftime('%Y-%m-%d')
        analysis['daily_total'][date_str] += sleep.duration

        # Classify sleep type based on start time
        if _is_night_sleep(sleep.start_time.hour):
            analysis['daily_night'][date_str] += sleep.duration
        else:
            analysis['daily_naps'][date_str] += 1
            analysis['daily_nap_duration'][date_str] += sleep.duration

        # Track location
        if sleep.location:
            location_value = _get_enum_value(sleep.location)
            analysis['locations'][location_value] += 1

        # Track quality
        if sleep.quality:
            quality_value = _get_enum_value(sleep.quality)
            analysis['qualities'].append(quality_value)

    return analysis


def _get_enum_value(enum_or_str) -> str:
    """Extract string value from enum or return string as-is."""
    return enum_or_str.value if hasattr(enum_or_str, 'value') else str(enum_or_str)


def _calculate_age_months(birthdate: datetime) -> Optional[int]:
    """Calculate age in months from birthdate."""
    if not birthdate:
        return None
    age_days = (datetime.utcnow() - birthdate).days
    return age_days // MONTHS_PER_YEAR


def _create_sleep_summary(analysis: Dict[str, Any], days: int, baby_age_months: Optional[int]) -> Dict[str, Any]:
    """
    Create summary statistics from sleep analysis.

    Note: Averages are calculated over the entire period, not just days with data.
    """
    # Calculate totals
    total_sleep = sum(analysis['daily_total'].values())
    total_night = sum(analysis['daily_night'].values())
    total_nap_duration = sum(analysis['daily_nap_duration'].values())
    total_naps = sum(analysis['daily_naps'].values())
    days_with_data = len(analysis['daily_total'])

    # Calculate averages (over entire period)
    avg_total = total_sleep / days
    avg_night = total_night / days
    avg_nap_duration = total_nap_duration / days
    avg_naps = total_naps / days

    return {
        'avg_total_sleep_minutes': round(avg_total, 1),
        'avg_total_sleep_hours': round(avg_total / 60, 2),
        'avg_night_sleep_minutes': round(avg_night, 1),
        'avg_night_sleep_hours': round(avg_night / 60, 2),
        'avg_nap_duration_minutes': round(avg_nap_duration, 1),
        'avg_nap_duration_hours': round(avg_nap_duration / 60, 2),
        'avg_naps_per_day': round(avg_naps, 2),
        'total_days_analyzed': days,
        'days_with_sleep_data': days_with_data
    }


def _format_daily_sleep(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Format daily sleep data for response."""
    return [
        {
            'date': date,
            'total_minutes': minutes,
            'total_hours': round(minutes / 60, 2),
            'night_minutes': analysis['daily_night'].get(date, 0),
            'nap_minutes': analysis['daily_nap_duration'].get(date, 0),
            'nap_count': analysis['daily_naps'].get(date, 0)
        }
        for date, minutes in sorted(analysis['daily_total'].items())
    ]


def _get_age_category(baby_age_months: Optional[int]) -> Dict[str, Any]:
    """Get age-appropriate sleep requirements based on baby's age."""
    if baby_age_months is None:
        return SLEEP_REQUIREMENTS[DEFAULT_AGE_CATEGORY]

    for category in SLEEP_REQUIREMENTS.values():
        min_age, max_age = category['age_range']
        if min_age <= baby_age_months <= max_age:
            return category

    return SLEEP_REQUIREMENTS['older_toddler']


def _calculate_sleep_quality(
        analysis: Dict[str, Any],
        summary: Dict[str, Any],
        baby_age_months: Optional[int],
        method: str
) -> Dict[str, Any]:
    """
    Calculate sleep quality score using the specified method.

    Args:
        analysis: Analyzed sleep data
        summary: Summary statistics
        baby_age_months: Baby's age in months
        method: Calculation method ("PSQI" or "custom")

    Returns:
        Dictionary containing quality score, rating, and explanation
    """
    # Handle no data case
    if summary['days_with_sleep_data'] == 0:
        return {
            'sleep_quality_score': 0,
            'sleep_quality_rating': "No Data",
            'sleep_quality_explanation': "No sleep data available for the selected period",
            'calculation_method': method
        }

    age_category = _get_age_category(baby_age_months)

    # Calculate score based on method
    if method == "PSQI":
        score, rating, explanation = _calculate_psqi_score(
            analysis, summary, age_category, baby_age_months
        )
    else:  # custom
        score, rating, explanation = _calculate_custom_score(
            analysis, summary, age_category, baby_age_months
        )

    return {
        'sleep_quality_score': round(score, 1),
        'sleep_quality_rating': rating,
        'sleep_quality_explanation': explanation,
        'calculation_method': method
    }


def _calculate_psqi_score(
        analysis: Dict[str, Any],
        summary: Dict[str, Any],
        age_category: Dict[str, Any],
        baby_age_months: Optional[int]
) -> Tuple[float, str, str]:
    """
    Calculate PSQI-inspired sleep score (0-100).

    Component weights:
    - Sleep Duration (25%): Age-appropriate sleep amount
    - Sleep Quality (20%): Subjective sleep quality ratings
    - Sleep Efficiency (20%): Data completeness and consistency
    - Sleep Pattern (20%): Night vs day sleep distribution
    - Nap Consistency (15%): Age-appropriate nap frequency
    """
    components = {}
    raw_scores = {}  # Store raw scores (0-100) for each component
    avg_total_hours = summary['avg_total_sleep_hours']

    # 1. Sleep Duration Component
    raw_scores['duration'] = _calculate_duration_score(avg_total_hours, age_category)
    components['duration'] = raw_scores['duration'] * 0.25

    # 2. Sleep Quality Component
    raw_scores['quality'] = _calculate_quality_score(analysis['qualities'], avg_total_hours)
    components['quality'] = raw_scores['quality'] * 0.20

    # 3. Sleep Efficiency Component
    raw_scores['efficiency'] = _calculate_efficiency_score(summary, avg_total_hours)
    components['efficiency'] = raw_scores['efficiency'] * 0.20

    # 4. Sleep Pattern Component
    raw_scores['pattern'] = _calculate_pattern_score(summary, age_category, avg_total_hours)
    components['pattern'] = raw_scores['pattern'] * 0.20

    # 5. Nap Consistency Component
    raw_scores['nap_consistency'] = _calculate_nap_score(summary, age_category, avg_total_hours)
    components['nap_consistency'] = raw_scores['nap_consistency'] * 0.15

    # Calculate final score
    final_score = sum(components.values())
    rating = _get_score_rating(final_score)

    # Create explanation with weighted contributions
    age_context = f" ({age_category['name']})" if baby_age_months is not None else ""

    # Show how much each component contributed to the final score
    explanation = (
        f"PSQI-Inspired Score: {final_score:.1f}/100{age_context}. "
        f"Contributions - Duration: {components['duration']:.1f}/25, "
        f"Quality: {components['quality']:.1f}/20, "
        f"Efficiency: {components['efficiency']:.1f}/20, "
        f"Sleep Pattern: {components['pattern']:.1f}/20, "
        f"Nap Consistency: {components['nap_consistency']:.1f}/15"
    )

    return final_score, rating, explanation


def _calculate_duration_score(avg_total_hours: float, age_category: Dict[str, Any]) -> float:
    """Calculate sleep duration score (0-100) based on age-appropriate targets."""
    if avg_total_hours < MIN_ACCEPTABLE_SLEEP_HOURS:
        # Severe penalty for critically low sleep
        return 30 * (avg_total_hours / MIN_ACCEPTABLE_SLEEP_HOURS)

    target_min, target_max = age_category['sleep_range']

    if target_min <= avg_total_hours <= target_max:
        return 100
    elif avg_total_hours < target_min:
        deficit = target_min - avg_total_hours
        return max(30, 100 - (deficit * 15))
    else:
        excess = avg_total_hours - target_max
        return max(50, 100 - (excess * 10))


def _calculate_quality_score(qualities: List[str], avg_total_hours: float) -> float:
    """Calculate sleep quality score based on subjective ratings."""
    if not qualities:
        base_score = DEFAULT_QUALITY_SCORE
    else:
        quality_values = [QUALITY_SCORES.get(q, DEFAULT_QUALITY_SCORE) for q in qualities]
        base_score = sum(quality_values) / len(quality_values)

    # Apply penalty for low sleep
    if avg_total_hours < MIN_ACCEPTABLE_SLEEP_HOURS:
        base_score *= 0.5

    return base_score


def _calculate_efficiency_score(summary: Dict[str, Any], avg_total_hours: float) -> float:
    """Calculate sleep efficiency score based on data availability."""
    efficiency_ratio = summary['days_with_sleep_data'] / summary['total_days_analyzed']
    base_score = efficiency_ratio * 100

    # Apply penalty for low sleep
    if avg_total_hours < MIN_ACCEPTABLE_SLEEP_HOURS:
        base_score *= 0.5

    return base_score


def _calculate_pattern_score(summary: Dict[str, Any], age_category: Dict[str, Any], avg_total_hours: float) -> float:
    """Calculate sleep pattern score based on night/day distribution."""
    if summary['avg_total_sleep_minutes'] > 0:
        night_ratio = summary['avg_night_sleep_minutes'] / summary['avg_total_sleep_minutes']
    else:
        return 0

    min_night_ratio = age_category['min_night_ratio']

    if night_ratio >= min_night_ratio:
        base_score = 100
    else:
        base_score = (night_ratio / min_night_ratio) * 100

    # Apply penalty for low sleep
    if avg_total_hours < MIN_ACCEPTABLE_SLEEP_HOURS:
        base_score *= 0.5

    return base_score


def _calculate_nap_score(summary: Dict[str, Any], age_category: Dict[str, Any], avg_total_hours: float) -> float:
    """Calculate nap consistency score based on age-appropriate nap frequency."""
    nap_min, nap_max = age_category['nap_range']
    avg_naps = summary['avg_naps_per_day']

    if nap_min <= avg_naps <= nap_max:
        base_score = 100
    else:
        deviation = min(abs(avg_naps - nap_min), abs(avg_naps - nap_max))
        base_score = max(0, 100 - (deviation * 25))

    # Apply penalty for low sleep
    if avg_total_hours < MIN_ACCEPTABLE_SLEEP_HOURS:
        base_score *= 0.5

    return base_score


def _calculate_custom_score(
        analysis: Dict[str, Any],
        summary: Dict[str, Any],
        age_category: Dict[str, Any],
        baby_age_months: Optional[int]
) -> Tuple[float, str, str]:
    """
    Calculate custom sleep score (0-100).

    Point distribution:
    - Total sleep duration: 35 points
    - Night sleep proportion: 25 points
    - Data consistency: 20 points
    - Sleep quality ratings: 15 points
    - Sleep location consistency: 5 points
    """
    components = {}

    # 1. Total sleep duration (35 points)
    components['duration'] = _calculate_custom_duration_points(
        summary['avg_total_sleep_hours'],
        age_category
    )

    # 2. Night sleep proportion (25 points)
    components['night_proportion'] = _calculate_custom_night_points(
        summary,
        age_category
    )

    # 3. Data consistency (20 points)
    components['consistency'] = _calculate_custom_consistency_points(
        summary
    )

    # 4. Sleep quality ratings (15 points)
    components['quality'] = _calculate_custom_quality_points(
        analysis['qualities'],
        summary['avg_total_sleep_hours']
    )

    # 5. Sleep location consistency (5 points)
    components['location'] = _calculate_custom_location_points(
        analysis['locations']
    )

    # Calculate final score
    final_score = sum(components.values())
    rating = _get_score_rating(final_score)

    # Create explanation
    age_context = f" (Age: {baby_age_months} months)" if baby_age_months is not None else ""

    # Show percentage of max possible points for each component
    explanation = (
        f"Custom Score: {final_score:.1f}/100{age_context}. "
        f"Component scores - Duration: {components['duration']:.0f}/35 , "
        f"Night ratio: {components['night_proportion']:.0f}/25 , "
        f"Consistency: {components['consistency']:.0f}/20 , "
        f"Quality: {components['quality']:.0f}/15 , "
        f"Location: {components['location']:.0f}/5 "
    )

    return final_score, rating, explanation


def _calculate_custom_duration_points(avg_total_hours: float, age_category: Dict[str, Any]) -> float:
    """Calculate duration points for custom scoring (max 35 points)."""
    if avg_total_hours < MIN_ACCEPTABLE_SLEEP_HOURS:
        return 10 * (avg_total_hours / MIN_ACCEPTABLE_SLEEP_HOURS)

    target_min, _ = age_category['sleep_range']
    midpoint = age_category['sleep_midpoint']

    if avg_total_hours >= midpoint:
        return 35
    elif avg_total_hours >= target_min:
        return 30
    elif avg_total_hours >= target_min - 2:
        return 20
    else:
        return max(10, avg_total_hours * 2)


def _calculate_custom_night_points(summary: Dict[str, Any], age_category: Dict[str, Any]) -> float:
    """Calculate night sleep proportion points (max 25 points)."""
    if summary['avg_total_sleep_minutes'] <= 0:
        return 0

    night_proportion = summary['avg_night_sleep_minutes'] / summary['avg_total_sleep_minutes']
    min_night_ratio = age_category['min_night_ratio']

    if night_proportion >= min_night_ratio:
        points = 25
    else:
        points = (night_proportion / min_night_ratio) * 25

    # Apply penalty for low total sleep
    if summary['avg_total_sleep_hours'] < MIN_ACCEPTABLE_SLEEP_HOURS:
        points *= 0.3

    return points


def _calculate_custom_consistency_points(summary: Dict[str, Any]) -> float:
    """Calculate data consistency points (max 20 points)."""
    consistency_ratio = summary['days_with_sleep_data'] / summary['total_days_analyzed']
    points = consistency_ratio * 20

    # Apply penalty for low average sleep
    if summary['avg_total_sleep_hours'] < MIN_ACCEPTABLE_SLEEP_HOURS:
        points *= 0.5

    return points


def _calculate_custom_quality_points(qualities: List[str], avg_total_hours: float) -> float:
    """Calculate quality rating points (max 15 points)."""
    if not qualities:
        points = 7.5  # Default to middle
    else:
        quality_values = [QUALITY_SCORES.get(q, DEFAULT_QUALITY_SCORE) for q in qualities]
        avg_quality = sum(quality_values) / len(quality_values)
        points = (avg_quality / 100) * 15

    # Apply penalty for low sleep
    if avg_total_hours < MIN_ACCEPTABLE_SLEEP_HOURS:
        points *= 0.5

    return points


def _calculate_custom_location_points(locations: Dict[str, int]) -> float:
    """Calculate location consistency points (max 5 points)."""
    if not locations:
        return 2.5  # Default to middle

    total_locations = sum(locations.values())
    if total_locations == 0:
        return 2.5

    max_location_count = max(locations.values())
    location_consistency = max_location_count / total_locations
    return location_consistency * 5


def _get_score_rating(score: float) -> str:
    """Convert numeric score to qualitative rating."""
    if score >= 85:
        return "Excellent"
    elif score >= 70:
        return "Good"
    elif score >= 50:
        return "Fair"
    else:
        return "Poor"