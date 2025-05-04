from typing import List, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.user import User
from app.main.service.notification_service import (
    get_user_notifications,
    mark_notification_read,
    mark_all_notifications_read
)
from app.main.service.oauth_service import get_current_user

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    responses={404: {"description": "Not found"}}
)

class NotificationResponse(BaseModel):
    id: int
    created_at: Any
    message: str
    type: str
    reference_id: Optional[int] = None
    is_read: bool

class NotificationActionResponse(BaseModel):
    status: str
    message: str


@router.get("/", response_model=List[NotificationResponse])
async def get_my_notifications(
    unread_only: bool = Query(False, description="Get only unread notifications"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all notifications for the current user"""
    return get_user_notifications(db, current_user.id, unread_only)


@router.put("/{notification_id}/read", response_model=NotificationActionResponse)
async def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a notification as read"""
    result = mark_notification_read(db, notification_id, current_user.id)
    
    if isinstance(result, dict) and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get('message', 'Notification not found')
        )
    
    return result


@router.put("/mark-all-read", response_model=NotificationActionResponse)
async def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark all notifications as read"""
    return mark_all_notifications_read(db, current_user.id)
