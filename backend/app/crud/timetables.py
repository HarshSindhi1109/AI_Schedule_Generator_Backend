from sqlalchemy.orm import Session
from app.models.timetables import Timetable
from uuid import UUID

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