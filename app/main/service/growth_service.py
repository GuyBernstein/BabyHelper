from datetime import datetime
from typing import Dict, List, Union, Any, Optional, Type

from sqlalchemy.orm import Session

from app.main.model import User
from app.main.model.growth import Growth
from app.main.service.baby_service import get_baby_if_authorized
from app.main.service.growth_percentile_service import calculate_growth_percentile


def create_growth(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Growth, Dict[str, str]]:
    """Create a new growth measurement record for a baby with percentile calculations"""
    # Check if user is authorized to add growth records for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Create new growth record
    new_growth = Growth(
        created_at=datetime.utcnow(),
        measurement_date=data['measurement_date'],
        weight=data.get('weight'),
        height=data.get('height'),
        head_circumference=data.get('head_circumference'),
        notes=data.get('notes'),
        baby_id=data['baby_id'],
        recorded_by=current_user_id
    )

    # Calculate percentiles based on WHO growth standards
    percentile_data = _calculate_percentiles(
        baby=baby,
        measurement_date=data['measurement_date'],
        weight=data.get('weight'),
        height=data.get('height'),
        head_circumference=data.get('head_circumference')
    )

    if percentile_data and percentile_data['status'] == 'success':
        new_growth.percentile_data = percentile_data

    db.add(new_growth)
    db.commit()
    db.refresh(new_growth)

    caregiver = db.query(User).filter(User.id == new_growth.recorded_by).first()
    if caregiver:
        new_growth.caregiver_name = caregiver.name

    return new_growth


def get_growths_for_baby(db: Session, baby_id: int, current_user_id: int,
                         skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> Union[dict[str, str], list[Type[Growth]]]:
    """Get growth measurement records for a baby with optional date filtering"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query growth records
    query = db.query(Growth).filter(Growth.baby_id == baby_id)

    # Apply date filters if provided
    if start_date:
        query = query.filter(Growth.measurement_date >= start_date)
    if end_date:
        query = query.filter(Growth.measurement_date <= end_date)

    # Order by date descending (newest first)
    query = query.order_by(Growth.measurement_date.desc())

    # Apply pagination
    growths = query.offset(skip).limit(limit).all()

    # Add caregiver information to each growth record
    for growth in growths:
        caregiver = db.query(User).filter(User.id == growth.recorded_by).first()
        if caregiver:
            growth.caregiver_name = caregiver.name

    return growths


def get_growth(db: Session, growth_id: int, current_user_id: int) -> Union[Growth, Dict[str, str]]:
    """Get a specific growth measurement record by ID"""
    # Get the growth record
    growth = db.query(Growth).filter(Growth.id == growth_id).first()

    if not growth:
        return {
            'status': 'fail',
            'message': 'Growth measurement record not found',
        }

    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, growth.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    caregiver = db.query(User).filter(User.id == growth.recorded_by).first()
    if caregiver:
        growth.caregiver_name = caregiver.name

    return growth


def update_growth(db: Session, growth_id: int, data: Dict[str, Any], current_user_id: int) -> Union[
    dict[str, str], dict[str, str], Type[Growth]]:
    """Update a growth measurement record with recalculated percentiles"""
    # Get the growth record
    growth = db.query(Growth).filter(Growth.id == growth_id).first()

    if not growth:
        return {
            'status': 'fail',
            'message': 'Growth measurement record not found',
        }

    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, growth.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Update growth record
    growth.measurement_date = data.get('measurement_date', growth.measurement_date)
    growth.weight = data.get('weight', growth.weight)
    growth.height = data.get('height', growth.height)
    growth.head_circumference = data.get('head_circumference', growth.head_circumference)
    growth.notes = data.get('notes', growth.notes)

    # Recalculate percentiles based on WHO growth standards
    percentile_data = _calculate_percentiles(
        baby=baby,
        measurement_date=growth.measurement_date,
        weight=growth.weight,
        height=growth.height,
        head_circumference=growth.head_circumference
    )

    if percentile_data and percentile_data['status'] == 'success':
        growth.percentile_data = percentile_data

    db.commit()
    db.refresh(growth)

    caregiver = db.query(User).filter(User.id == growth.recorded_by).first()
    if caregiver:
        growth.caregiver_name = caregiver.name

    return growth


def delete_growth(db: Session, growth_id: int, current_user_id: int) -> Union[Dict[str, str], None]:
    """Delete a growth measurement record"""
    # Get the growth record
    growth = db.query(Growth).filter(Growth.id == growth_id).first()

    if not growth:
        return {
            'status': 'fail',
            'message': 'Growth measurement record not found',
        }

    # Check if user is authorized to update this baby's data
    baby = get_baby_if_authorized(db, growth.baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Delete the growth record
    db.delete(growth)
    db.commit()
    return {'status': 'DELETED'}


def _calculate_percentiles(baby, measurement_date, weight, height, head_circumference):
    """Calculate percentiles using the WHO growth percentile service"""
    # Prepare baby data for percentile calculation
    baby_data = {
        'birthdate': baby.birthdate,
        'sex': baby.sex
    }

    # Prepare measurement data
    measurement_data = {
        'weight': weight,
        'height': height,
        'head_circumference': head_circumference
    }

    # Calculate growth percentiles
    try:
        percentile_result = calculate_growth_percentile(
            baby_data=baby_data,
            measurement_data=measurement_data,
            measurement_date=measurement_date
        )
        return percentile_result
    except Exception as e:
        # Log the error but don't fail the entire operation
        print(f"Error calculating percentiles: {str(e)}")
        return None