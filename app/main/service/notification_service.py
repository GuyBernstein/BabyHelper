from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_

# Import Notification from the updated schema
from app.main.model.parent_child_schema import Notification, CoParentInvitation


def create_notification(db: Session, user_id: int, message: str, notification_type: str, reference_id: Optional[int] = None) -> Notification:
    """Create a new notification for a user"""
    notification = Notification(
        created_at=datetime.utcnow(),
        user_id=user_id,
        message=message,
        type=notification_type,
        reference_id=reference_id,
        is_read=False
    )
    
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_user_notifications(db: Session, user_id: int, unread_only: bool = False) -> List[Dict[str, Any]]:
    """Get notifications for a user"""
    query = db.query(Notification).filter(Notification.user_id == user_id)
    
    if unread_only:
        query = query.filter(Notification.is_read == False)
    
    # Order by newest first
    notifications = query.order_by(Notification.created_at.desc()).all()
    
    # Convert to dictionaries for the response
    notification_list = []
    for notification in notifications:
        notification_list.append({
            'id': notification.id,
            'created_at': notification.created_at,
            'message': notification.message,
            'type': notification.type,
            'reference_id': notification.reference_id,
            'is_read': notification.is_read
        })
    
    return notification_list


def mark_notification_read(db: Session, notification_id: int, user_id: int) -> Union[Dict[str, str], Dict[str, str]]:
    """Mark a notification as read"""
    notification = db.query(Notification).filter(
        and_(
            Notification.id == notification_id,
            Notification.user_id == user_id
        )
    ).first()
    
    if not notification:
        return {
            'status': 'fail',
            'message': 'Notification not found',
        }
    
    notification.is_read = True
    db.commit()
    
    return {
        'status': 'success',
        'message': 'Notification marked as read',
    }


def mark_all_notifications_read(db: Session, user_id: int) -> Dict[str, str]:
    """Mark all notifications for a user as read"""
    db.query(Notification).filter(
        and_(
            Notification.user_id == user_id,
            Notification.is_read == False
        )
    ).update({Notification.is_read: True})
    
    db.commit()
    
    return {
        'status': 'success',
        'message': 'All notifications marked as read',
    }


def remove_sent_notification(db, notification_id, user_id=None):
    # Get the notification
    notification = db.query(Notification).filter(Notification.id == notification_id).first()

    if not notification:
        return {
            'status': 'fail',
            'message': 'Notification not found',
        }

    # Optional: Check if user is authorized (either the sender or receiver)
    if user_id and notification.type == 'coparent_invitation' and notification.reference_id:
        invitation = db.query(CoParentInvitation).filter(
            CoParentInvitation.id == notification.reference_id
        ).first()

        if invitation and invitation.inviter_id != user_id:
            return {
                'status': 'fail',
                'message': 'Not authorized to remove this invitation',
            }

    # If it's a coparent invitation notification, also delete the invitation
    if notification.type == 'coparent_invitation' and notification.reference_id:
        db.query(CoParentInvitation).filter(
            CoParentInvitation.id == notification.reference_id
        ).delete()

    # Delete the notification
    db.query(Notification).filter(Notification.id == notification_id).delete()
    db.commit()

    return {
        'status': 'success',
        'message': 'Notification and associated invitation have been deleted',
    }