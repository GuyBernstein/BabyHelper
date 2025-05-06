from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.growth import router, GrowthCreate, GrowthUpdate, GrowthResponse
from app.main.model.user import User
from app.main.service.growth_service import (
    create_growth,
    get_growths_for_baby,
    get_growth,
    update_growth,
    delete_growth
)
from app.main.service.baby_service import get_baby_if_authorized
from app.main.service.growth_percentile_service import calculate_growth_percentile
from app.main.service.oauth_service import get_current_user


@router.post("/", response_model=GrowthResponse, status_code=status.HTTP_201_CREATED)
async def create_growth_record(
        growth: GrowthCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new growth measurement record (requires authentication and parent/co-parent relationship)"""
    # First create the growth record
    result = create_growth(db, growth.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to create growth record')
        )

    # Get the baby data for percentile calculation
    baby = get_baby_if_authorized(db, growth.baby_id, current_user.id)
    if isinstance(baby, dict):  # Error response
        return result  # Return the growth record without percentiles

    # Prepare baby data for percentile calculation
    baby_data = {
        'birthdate': baby.birthdate,
        'sex': baby.sex
    }

    # Prepare measurement data
    measurement_data = {
        'weight': growth.weight,
        'height': growth.height,
        'head_circumference': growth.head_circumference
    }

    # Calculate growth percentiles
    try:
        # Ensure measurement_date is timezone naive to match birthdate format
        measurement_date = growth.measurement_date
        if hasattr(measurement_date, 'tzinfo') and measurement_date.tzinfo is not None:
            # Convert to naive datetime by removing timezone info
            measurement_date = measurement_date.replace(tzinfo=None)

        percentile_result = calculate_growth_percentile(
            baby_data=baby_data,
            measurement_data=measurement_data,
            measurement_date=measurement_date
        )

        if percentile_result['status'] == 'success':
            # Update the growth record with the percentile data
            # We need to access the created record directly
            growth_record = get_growth(db, result.id, current_user.id)
            if not isinstance(growth_record, dict):  # Not an error response
                # Update the percentile_data field with the calculated percentiles
                growth_record.percentile_data = percentile_result.get('percentiles')
                db.commit()

                # Update the result to include the percentiles
                result.percentiles = percentile_result.get('percentiles')
                result.baby_age_months = percentile_result.get('baby_age_months')
    except Exception as e:
        # Log the error but don't fail the whole operation
        print(f"Error calculating percentiles: {str(e)}")
        # Growth record was still created, just without percentiles

    return result


@router.get("/baby/{baby_id}", response_model=List[GrowthResponse])
async def get_growths_by_baby(
        baby_id: int,
        skip: int = Query(0, description="Skip N records"),
        limit: int = Query(100, description="Limit to N records"),
        start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
        end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get growth measurement records for a baby (requires authentication and parent/co-parent relationship)"""
    result = get_growths_for_baby(db, baby_id, current_user.id, skip, limit, start_date, end_date)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve growth records')
        )

    # Process each growth record to ensure percentiles and baby_age_months are set
    # Handle both single record and list of records
    if isinstance(result, list):
        for record in result:
            if hasattr(record, 'percentile_data') and record.percentile_data:
                record.percentiles = record.percentile_data

                # Extract baby_age_months from the first percentile entry if available
                if record.percentiles and isinstance(record.percentiles, dict):
                    first_percentile = next(iter(record.percentiles.values()), None)
                    if first_percentile and isinstance(first_percentile, dict) and 'age_months' in first_percentile:
                        record.baby_age_months = first_percentile['age_months']

    return result


@router.get("/{growth_id}", response_model=GrowthResponse)
async def get_growth_record(
        growth_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get a specific growth measurement record (requires authentication and parent/co-parent relationship)"""
    result = get_growth(db, growth_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to retrieve growth record')
        )

    # Map the percentile_data to percentiles in the response
    if hasattr(result, 'percentile_data') and result.percentile_data:
        result.percentiles = result.percentile_data

        # Extract baby_age_months from the first percentile entry if available
        if result.percentiles and isinstance(result.percentiles, dict):
            first_percentile = next(iter(result.percentiles.values()), None)
            if first_percentile and isinstance(first_percentile, dict) and 'age_months' in first_percentile:
                result.baby_age_months = first_percentile['age_months']

    return result


@router.put("/{growth_id}", response_model=GrowthResponse)
async def update_growth_record(
        growth_id: int,
        growth_data: GrowthUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update a growth measurement record (requires authentication and parent/co-parent relationship)"""
    # First, get the existing growth record to get the baby_id
    existing_growth = get_growth(db, growth_id, current_user.id)
    if isinstance(existing_growth, dict) and existing_growth.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if existing_growth.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=existing_growth.get('message', 'Failed to retrieve growth record')
        )

    # Update the growth record
    result = update_growth(db, growth_id, growth_data.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to update growth record')
        )

    # Get the baby data for percentile calculation
    baby_id = existing_growth.baby_id
    baby = get_baby_if_authorized(db, baby_id, current_user.id)
    if isinstance(baby, dict):  # Error response
        return result  # Return the updated growth record without percentiles

    # Prepare baby data for percentile calculation
    baby_data = {
        'birthdate': baby.birthdate,
        'sex': baby.sex
    }

    # Prepare measurement data
    measurement_data = {
        'weight': growth_data.weight if growth_data.weight is not None else existing_growth.weight,
        'height': growth_data.height if growth_data.height is not None else existing_growth.height,
        'head_circumference': growth_data.head_circumference if growth_data.head_circumference is not None else existing_growth.head_circumference
    }

    # Calculate growth percentiles
    try:
        # Ensure measurement_date is timezone naive to match birthdate format
        measurement_date = growth_data.measurement_date
        if hasattr(measurement_date, 'tzinfo') and measurement_date.tzinfo is not None:
            # Convert to naive datetime by removing timezone info
            measurement_date = measurement_date.replace(tzinfo=None)

        percentile_result = calculate_growth_percentile(
            baby_data=baby_data,
            measurement_data=measurement_data,
            measurement_date=measurement_date
        )

        if percentile_result['status'] == 'success':
            # Update the growth record with the percentile data
            growth_record = get_growth(db, growth_id, current_user.id)
            if not isinstance(growth_record, dict):  # Not an error response
                # Update the percentile_data field with the calculated percentiles
                growth_record.percentile_data = percentile_result.get('percentiles')
                db.commit()

                # Update the result to include the percentiles
                result.percentiles = percentile_result.get('percentiles')
                result.baby_age_months = percentile_result.get('baby_age_months')
    except Exception as e:
        # Log the error but don't fail the whole operation
        print(f"Error calculating percentiles: {str(e)}")
        # Growth record was still updated, just without percentiles

    return result


@router.delete("/{growth_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_growth_record(
        growth_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete a growth measurement record (requires authentication and parent/co-parent relationship)"""
    result = delete_growth(db, growth_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_403_FORBIDDEN if result.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to delete growth record')
        )

    return None


@router.post("/calculate-percentiles", response_model=Dict[str, Any])
async def calculate_percentiles(
        baby_id: int,
        weight: Optional[float] = Query(None, description="Weight in kg"),
        height: Optional[float] = Query(None, description="Height in cm"),
        head_circumference: Optional[float] = Query(None, description="Head circumference in cm"),
        measurement_date: Optional[datetime] = Query(None, description="Measurement date (defaults to current date)"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """
    Calculate growth percentiles without saving a growth record
    (requires authentication and parent/co-parent relationship)
    """
    # Check if user is authorized to access this baby's data
    baby = get_baby_if_authorized(db, baby_id, current_user.id)
    if isinstance(baby, dict):  # Error response
        status_code = status.HTTP_403_FORBIDDEN if baby.get(
            'message') == 'Not authorized to access this baby' else status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail=baby.get('message', 'Baby not found')
        )

    # If no measurement date provided, use current date
    if measurement_date is None:
        measurement_date = datetime.utcnow()

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
        result = calculate_growth_percentile(
            baby_data=baby_data,
            measurement_data=measurement_data,
            measurement_date=measurement_date
        )

        if result['status'] == 'fail':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get('message', 'Failed to calculate percentiles')
            )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating percentiles: {str(e)}"
        )