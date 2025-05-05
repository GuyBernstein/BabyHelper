from datetime import datetime
from typing import Dict, List, Union, Any, Optional

from sqlalchemy.orm import Session

from app.main.model.growth import Growth
from app.main.service.baby_service import get_baby_if_authorized


def create_growth_record(db: Session, data: Dict[str, Any], current_user_id: int) -> Union[Growth, Dict[str, str]]:
    """Create a new growth record for a baby"""
    # Check if user is authorized to add growth records for this baby
    baby = get_baby_if_authorized(db, data['baby_id'], current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Create new growth record
    new_growth = Growth(
        created_at=datetime.utcnow(),
        date=data['date'],
        weight=data.get('weight'),
        height=data.get('height'),
        head_circumference=data.get('head_circumference'),
        notes=data.get('notes'),
        baby_id=data['baby_id']
    )

    db.add(new_growth)
    db.commit()
    db.refresh(new_growth)
    return new_growth


def get_growth_records_for_baby(db: Session, baby_id: int, current_user_id: int,
                                skip: int = 0, limit: int = 100, start_date: Optional[datetime] = None,
                                end_date: Optional[datetime] = None) -> Union[List[Growth], Dict[str, str]]:
    """Get growth records for a baby with optional date filtering"""
    # Check if user is authorized to view this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Query growth records
    query = db.query(Growth).filter(Growth.baby_id == baby_id)

    # Apply date filters if provided
    if start_date:
        query = query.filter(Growth.date >= start_date)
    if end_date:
        query = query.filter(Growth.date <= end_date)

    # Order by date descending (newest first)
    query = query.order_by(Growth.date.desc())

    # Apply pagination
    growth_records = query.offset(skip).limit(limit).all()

    return growth_records