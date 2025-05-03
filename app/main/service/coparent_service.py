from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.main.model.baby import Baby
from app.main.model.user import User
from app.main.service.baby_service import get_baby_if_authorized
from app.main.service.notification_service import create_notification

# Import CoParentInvitation from the updated schema
from app.main.model.parent_child_schema import CoParentInvitation, Notification

def send_coparent_invitation(db: Session, baby_id: int, invitee_email: str, inviter_id: int) -> Union[CoParentInvitation, Dict[str, str]]:
    """Send a co-parent invitation to another user"""
    # Check if the baby exists and the inviter is the parent
    baby = db.query(Baby).filter(Baby.id == baby_id).first()
    if not baby:
        return {
            'status': 'fail',
            'message': 'Baby not found',
        }

    # Only the primary parent can send invitations
    if baby.parent_id != inviter_id:
        return {
            'status': 'fail',
            'message': 'Only the primary parent can send co-parent invitations',
        }

    # Check if the invitee exists
    invitee = db.query(User).filter(User.email == invitee_email).first()
    if not invitee:
        return {
            'status': 'fail',
            'message': 'The invited user does not exist',
        }

    # Check if invitee is already a co-parent
    for coparent in baby.coparents:
        if coparent.id == invitee.id:
            return {
                'status': 'fail',
                'message': 'User is already a co-parent for this baby',
            }

    # Check if there's already a pending invitation
    existing_invitation = db.query(CoParentInvitation).filter(
        and_(
            CoParentInvitation.baby_id == baby_id,
            CoParentInvitation.invitee_id == invitee.id,
            CoParentInvitation.status == 'pending'
        )
    ).first()

    if existing_invitation:
        return {
            'status': 'fail',
            'message': 'There is already a pending invitation for this user',
        }

    # Create the invitation
    invitation = CoParentInvitation(
        created_at=datetime.utcnow(),
        inviter_id=inviter_id,
        invitee_id=invitee.id,
        baby_id=baby_id,
        status='pending'
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    # Create a notification for the invitee
    inviter = db.query(User).filter(User.id == inviter_id).first()
    message = f"{inviter.name} has invited you to be a co-parent for {baby.fullname}"
    create_notification(db, invitee.id, message, "coparent_invitation", invitation.id)

    return invitation


def get_pending_invitations(db: Session, user_id: int) -> List[Dict[str, Any]]:
    """Get all pending co-parent invitations for a user"""
    invitations = db.query(CoParentInvitation).filter(
        and_(
            CoParentInvitation.invitee_id == user_id,
            CoParentInvitation.status == 'pending'
        )
    ).all()

    # Prepare a detailed response with baby and inviter information
    detailed_invitations = []
    for invitation in invitations:
        baby = db.query(Baby).filter(Baby.id == invitation.baby_id).first()
        inviter = db.query(User).filter(User.id == invitation.inviter_id).first()
        
        detailed_invitations.append({
            'invitation_id': invitation.id,
            'created_at': invitation.created_at,
            'baby_id': baby.id,
            'baby_name': baby.fullname,
            'inviter_id': inviter.id,
            'inviter_name': inviter.name,
            'inviter_email': inviter.email,
            'status': invitation.status
        })

    return detailed_invitations


def respond_to_invitation(db: Session, invitation_id: int, user_id: int, accept: bool) -> Union[Dict[str, str], Dict[str, str]]:
    """Accept or reject a co-parent invitation"""
    # Find the invitation
    invitation = db.query(CoParentInvitation).filter(
        and_(
            CoParentInvitation.id == invitation_id,
            CoParentInvitation.invitee_id == user_id,
            CoParentInvitation.status == 'pending'
        )
    ).first()

    if not invitation:
        return {
            'status': 'fail',
            'message': 'Invitation not found or already processed',
        }

    # Update the invitation status
    invitation.status = 'accepted' if accept else 'rejected'
    db.commit()

    # If accepted, add the co-parent relationship
    if accept:
        baby = db.query(Baby).filter(Baby.id == invitation.baby_id).first()
        invitee = db.query(User).filter(User.id == user_id).first()
        
        # Add the user as a co-parent
        if invitee not in baby.coparents:
            baby.coparents.append(invitee)
            db.commit()
        
        # Create a notification for the inviter
        message = f"{invitee.name} has accepted your co-parent invitation for {baby.fullname}"
        create_notification(db, invitation.inviter_id, message, "coparent_accepted", invitation.id)
        
        return {
            'status': 'success',
            'message': f'You are now a co-parent for {baby.fullname}',
        }
    else:
        # Create a notification for the inviter that invitation was rejected
        invitee = db.query(User).filter(User.id == user_id).first()
        baby = db.query(Baby).filter(Baby.id == invitation.baby_id).first()
        message = f"{invitee.name} has declined your co-parent invitation for {baby.fullname}"
        create_notification(db, invitation.inviter_id, message, "coparent_rejected", invitation.id)
        
        return {
            'status': 'success',
            'message': 'Invitation declined',
        }


def remove_coparent(db: Session, baby_id: int, coparent_id: int, current_user_id: int) -> Dict[str, str]:
    """Remove a co-parent from a baby"""
    # Check if the baby exists and the current user is the parent
    baby = db.query(Baby).filter(Baby.id == baby_id).first()
    if not baby:
        return {
            'status': 'fail',
            'message': 'Baby not found',
        }

    # Only the primary parent can remove co-parents
    if baby.parent_id != current_user_id:
        return {
            'status': 'fail',
            'message': 'Only the primary parent can remove co-parents',
        }

    # Check if the user to remove is actually a co-parent
    coparent = db.query(User).filter(User.id == coparent_id).first()
    if not coparent:
        return {
            'status': 'fail',
            'message': 'User not found',
        }

    # Remove the co-parent relationship
    if coparent in baby.coparents:
        baby.coparents.remove(coparent)
        db.commit()
        
        # Create a notification for the removed co-parent
        message = f"You have been removed as a co-parent for {baby.fullname}"
        create_notification(db, coparent_id, message, "coparent_removed", baby_id)
        
        return {
            'status': 'success',
            'message': f'{coparent.name} has been removed as a co-parent',
        }
    else:
        return {
            'status': 'fail',
            'message': 'User is not a co-parent for this baby',
        }
