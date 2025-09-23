from sqlalchemy.orm import Session
from app.models.timetables import Timetable
from uuid import UUID
from datetime import datetime
from typing import Optional

def create_timetable(db: Session, timetable_data: dict):
    timetable = Timetable(**timetable_data)
    db.add(timetable)
    db.commit()
    db.refresh(timetable)
    return timetable

def get_all_timetables(db: Session):
    return db.query(Timetable).all()


def update_timetable(db: Session, timetable, updates: dict):
    for key, value in updates.items():
        setattr(timetable, key, value)
    db.commit()
    db.refresh(timetable)
    return timetable


def save_timetable_json(
        db: Session,
        dept: str,
        sem: int,
        user_id: str,  # This will be a string representation of UUID
        timetable_json: dict
) -> Timetable:
    # Convert string user_id to UUID object
    user_id_uuid = UUID(user_id)

    # Check if timetable already exists for this user
    existing = db.query(Timetable).filter_by(
        department_name=dept,
        semester_number=sem,
        user_id=user_id_uuid
    ).first()

    if existing:
        # Update existing timetable
        existing.timetable_json = timetable_json
        existing.created_at = datetime.now()
    else:
        # Create new timetable
        timetable_data = {
            "department_name": dept,
            "semester_number": sem,
            "user_id": user_id_uuid,
            "timetable_json": timetable_json,
            "created_at": datetime.now()
        }
        existing = create_timetable(db, timetable_data)

    db.commit()
    return existing

# timetables.py - Update the get_timetables_by_user function in CRUD
def get_timetables_by_user(db: Session, user_id: str):
    try:
        user_id_uuid = UUID(user_id)
        return db.query(Timetable).filter(Timetable.user_id== user_id_uuid).all()
    except ValueError as e:
        print(f"Invalid UUID format: {user_id}, error: {str(e)}")
        return []
    except Exception as e:
        print(f"Error querying timetables: {str(e)}")
        return []

def get_timetable(db: Session, timetable_id: int):
    """
    Get a timetable by ID.
    """
    return db.query(Timetable).filter(Timetable.id == timetable_id).first()

def delete_timetable(db: Session, timetable: Timetable):
    """
    Delete a timetable.
    """
    db.delete(timetable)
    db.commit()