from typing import List

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.baby import router, BabyCreate, BabyUpdate, BabyResponse
from app.main.service.baby_service import (
    get_all_babies,
    save_new_baby,
    get_a_baby,
    update_baby,
    delete_baby
)


@router.get("/", response_model=List[BabyResponse])
async def list_babies(db: Session = Depends(get_db)):
    """Get all babies"""
    return get_all_babies(db)


@router.post("/", response_model=BabyResponse, status_code=status.HTTP_201_CREATED)
async def create_baby(baby: BabyCreate, db: Session = Depends(get_db)):
    """Create a new baby"""
    result = save_new_baby(db, baby.model_dump())

    if isinstance(result, dict) and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.get('message', 'Baby already exists')
        )

    return result


@router.get("/{id}", response_model=BabyResponse)
async def get_baby(id: int, db: Session = Depends(get_db)):
    """Get a baby by ID"""
    baby = get_a_baby(db, id)
    if not baby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baby not found"
        )
    return baby


@router.put("/{id}", response_model=BabyResponse)
async def update_baby_info(id: int, baby_data: BabyUpdate, db: Session = Depends(get_db)):
    """Update a baby's information"""
    result = update_baby(db, id, baby_data.model_dump())

    if isinstance(result, dict) and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get('message', 'Baby not found')
        )

    return result


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_baby(id: int, db: Session = Depends(get_db)):
    """Delete a baby"""
    result = delete_baby(db, id)

    if result and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baby not found"
        )

    return None