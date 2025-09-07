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

def get_timetable(db: Session, id: int):
    return db.query(Timetable).filter_by(id=id).first()

def update_timetable(db: Session, timetable, updates: dict):
    for key, value in updates.items():
        setattr(timetable, key, value)
    db.commit()
    db.refresh(timetable)
    return timetable

def delete_timetable(db: Session, timetable):
    db.delete(timetable)
    db.commit()


def save_timetable_json(
        db: Session,
        dept: str,
        sem: int,
        user_id: Optional[int],
        timetable_json: dict
) -> Timetable:
    """
    Save or update timetable JSON data for a department/semester
    """
    # Check if timetable already exists
    existing = db.query(Timetable).filter_by(
        department_name=dept,
        semester_number=sem
    ).first()

    if existing:
        # Update existing timetable
        existing.timetable_json = timetable_json
        existing.generated_at = datetime.now()
        if user_id:
            existing.user_id = user_id
    else:
        # Create new timetable
        timetable_data = {
            "department_name": dept,
            "semester_number": sem,
            "timetable_json": timetable_json,
            "created_at": datetime.now()
        }
        if user_id:
            timetable_data["user_id"] = user_id

        existing = create_timetable(db, timetable_data)

    db.commit()
    return existing