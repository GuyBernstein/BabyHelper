from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Table, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.main import Base

# Association table for co-parent relationship
baby_coparent = Table(
    'baby_coparent',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('baby_id', Integer, ForeignKey('baby.id'), primary_key=True)
)

# Table for co-parent invitations
class CoParentInvitation(Base):
    __tablename__ = 'coparent_invitation'

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    inviter_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    invitee_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    baby_id = Column(Integer, ForeignKey('baby.id'), nullable=False)
    status = Column(String(20), default='pending')  # pending, accepted, rejected
    
    # Relationships
    inviter = relationship("User", foreign_keys=[inviter_id], back_populates="sent_invitations")
    invitee = relationship("User", foreign_keys=[invitee_id], back_populates="received_invitations")
    baby = relationship("Baby", back_populates="invitations")

    def __repr__(self):
        return f"<CoParentInvitation '{self.inviter_id}' -> '{self.invitee_id}' for baby '{self.baby_id}'>"

# Notification table for user alerts
class Notification(Base):
    __tablename__ = 'notification'

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    message = Column(String(500), nullable=False)
    type = Column(String(50), nullable=False)  # coparent_invitation, baby_update, etc.
    reference_id = Column(Integer, nullable=True)  # ID of the related entity (invitation, baby, etc.)
    is_read = Column(Boolean, default=False)
    
    # Relationship
    user = relationship("User", back_populates="notifications")

    def __repr__(self):
        return f"<Notification '{self.type}' for user '{self.user_id}'>"
