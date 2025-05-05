from datetime import datetime
from typing import Dict, Union, Any

from sqlalchemy.orm import Session

from app.main.model.milestone import Milestone, MilestoneCategory
from app.main.service.baby_service import get_baby_if_authorized


# Predefined milestones by age group
def get_standard_milestones():
    """Returns a list of standard developmental milestones by age"""
    return [
        # Motor milestones
        {"title": "Holds head up", "category": MilestoneCategory.MOTOR, "typical_age_months": 3},
        {"title": "Rolls over", "category": MilestoneCategory.MOTOR, "typical_age_months": 4},
        {"title": "Sits without support", "category": MilestoneCategory.MOTOR, "typical_age_months": 6},
        {"title": "Crawls", "category": MilestoneCategory.MOTOR, "typical_age_months": 9},
        {"title": "Walks alone", "category": MilestoneCategory.MOTOR, "typical_age_months": 12},

        # Language milestones
        {"title": "Coos and babbles", "category": MilestoneCategory.LANGUAGE, "typical_age_months": 3},
        {"title": "Says first word", "category": MilestoneCategory.LANGUAGE, "typical_age_months": 12},
        {"title": "Speaks in two-word phrases", "category": MilestoneCategory.LANGUAGE, "typical_age_months": 24},

        # Social milestones
        {"title": "Smiles socially", "category": MilestoneCategory.SOCIAL, "typical_age_months": 2},
        {"title": "Plays interactive games", "category": MilestoneCategory.SOCIAL, "typical_age_months": 12},
    ]


def add_standard_milestones(db: Session, baby_id: int, current_user_id: int) -> Union[Dict[str, Any], Dict[str, str]]:
    """Add all standard milestones to a baby's profile"""
    # Check if user is authorized to add milestones for this baby
    baby = get_baby_if_authorized(db, baby_id, current_user_id)
    if isinstance(baby, dict):  # Error response
        return baby

    # Get list of standard milestones
    standard_milestones = get_standard_milestones()

    # Check which milestones already exist to avoid duplicates
    existing_milestones = db.query(Milestone).filter(Milestone.baby_id == baby_id).all()
    existing_titles = {m.title for m in existing_milestones}

    # Add new milestones
    added_count = 0
    for m in standard_milestones:
        if m['title'] not in existing_titles:
            new_milestone = Milestone(
                created_at=datetime.utcnow(),
                title=m['title'],
                category=m['category'],
                typical_age_months=m['typical_age_months'],
                is_achieved=False,
                baby_id=baby_id
            )
            db.add(new_milestone)
            added_count += 1

    db.commit()

    return {
        'status': 'success',
        'message': f'Added {added_count} standard milestones',
        'added_count': added_count
    }