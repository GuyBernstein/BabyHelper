from typing import List

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.baby import router, BabyCreate, BabyUpdate, BabyResponse
from app.main.model.user import User
from app.main.service.baby_service import (
    get_all_babies_for_user,
    save_new_baby,
    get_a_baby,
    update_baby,
    delete_baby
)
from app.main.util.oauth import get_current_user


@router.get("/", response_model=List[BabyResponse])
async def list_babies(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get all babies for the current user (as parent or co-parent)"""
    return get_all_babies_for_user(db, current_user.id)


@router.post("/", response_model=BabyResponse, status_code=status.HTTP_201_CREATED)
async def create_baby(
        baby: BabyCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Create a new baby (requires authentication)"""
    result = save_new_baby(db, baby.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.get('message', 'Baby already exists')
        )

    return result


@router.get("/{id}", response_model=BabyResponse)
async def get_baby(
        id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get a baby by ID (requires authentication and parent/co-parent relationship)"""
    baby = get_a_baby(db, id, current_user.id)

    if isinstance(baby, dict) and baby.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if baby.get(
                'message') == 'Baby not found' else status.HTTP_403_FORBIDDEN,
            detail=baby.get('message', 'Baby not found')
        )

    return baby


@router.put("/{id}", response_model=BabyResponse)
async def update_baby_info(
        id: int,
        baby_data: BabyUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Update a baby's information (requires authentication and parent/co-parent relationship)"""
    result = update_baby(db, id, baby_data.model_dump(), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_404_NOT_FOUND
        if result.get('message') == 'Not authorized to access this baby':
            status_code = status.HTTP_403_FORBIDDEN

        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Baby not found')
        )

    return result


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_baby(
        id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Delete a baby (requires authentication and primary parent relationship)"""
    result = delete_baby(db, id, current_user.id)

    if result and result.get('status') == 'fail':
        status_code = status.HTTP_404_NOT_FOUND
        if result.get('message') == 'Only the primary parent can delete a baby':
            status_code = status.HTTP_403_FORBIDDEN

        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Baby not found')
        )

    return None