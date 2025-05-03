from typing import List, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.main import get_db
from app.main.model.user import User
from app.main.service.coparent_service import (
    send_coparent_invitation,
    get_pending_invitations,
    respond_to_invitation,
    remove_coparent
)
from app.main.util.oauth import get_current_user

router = APIRouter(
    prefix="/coparent",
    tags=["coparent"],
    responses={404: {"description": "Not found"}}
)


class CoParentInviteRequest(BaseModel):
    baby_id: int
    email: EmailStr


class InvitationResponse(BaseModel):
    status: str
    message: str


class PendingInvitationResponse(BaseModel):
    invitation_id: int
    created_at: Any
    baby_id: int
    baby_name: str
    inviter_id: int
    inviter_name: Optional[str]
    inviter_email: str
    status: str


class InvitationActionRequest(BaseModel):
    accept: bool


@router.post("/invite", response_model=InvitationResponse)
async def invite_coparent(
        request: CoParentInviteRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Invite another user to be a co-parent for a baby"""
    result = send_coparent_invitation(db, request.baby_id, str(request.email), current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_400_BAD_REQUEST
        if result.get('message') == 'Baby not found':
            status_code = status.HTTP_404_NOT_FOUND
        elif result.get('message') == 'Only the primary parent can send co-parent invitations':
            status_code = status.HTTP_403_FORBIDDEN

        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to send invitation')
        )

    return {
        "status": "success",
        "message": f"Invitation sent to {request.email}"
    }


@router.get("/invitations", response_model=List[PendingInvitationResponse])
async def get_my_pending_invitations(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Get all pending co-parent invitations for the current user"""
    return get_pending_invitations(db, current_user.id)


@router.post("/invitations/{invitation_id}", response_model=InvitationResponse)
async def respond_to_coparent_invitation(
        invitation_id: int,
        action: InvitationActionRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Accept or reject a co-parent invitation"""
    result = respond_to_invitation(db, invitation_id, current_user.id, action.accept)

    if isinstance(result, dict) and result.get('status') == 'fail':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get('message', 'Invitation not found')
        )

    return result


@router.delete("/baby/{baby_id}/coparent/{coparent_id}", response_model=InvitationResponse)
async def remove_baby_coparent(
        baby_id: int,
        coparent_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Remove a co-parent from a baby (requires being the primary parent)"""
    result = remove_coparent(db, baby_id, coparent_id, current_user.id)

    if isinstance(result, dict) and result.get('status') == 'fail':
        status_code = status.HTTP_400_BAD_REQUEST
        if result.get('message') == 'Baby not found' or result.get('message') == 'User not found':
            status_code = status.HTTP_404_NOT_FOUND
        elif result.get('message') == 'Only the primary parent can remove co-parents':
            status_code = status.HTTP_403_FORBIDDEN

        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', 'Failed to remove co-parent')
        )

    return result