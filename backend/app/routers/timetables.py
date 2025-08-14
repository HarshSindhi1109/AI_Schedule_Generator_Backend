from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from app.crud import timetables as crud_timetables
from app.database import SessionLocal
from app.models.timetables import Timetable
from app.schemas.timetables import TimetableBase, TimetableInput
from fastapi import Body
from app.services.layout_service import generate_timetable_layout

router = APIRouter(prefix="/timetables", tags=["Timetables"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=TimetableBase)
def create_timetable(timetable_data: TimetableBase, db: Session = Depends(get_db)):
    """
    Create a new timetable.
    """
    new_timetable = crud_timetables.create_timetable(db, timetable_data.dict())
    return {"message": "Timetable created successfully", "timetable": new_timetable}

@router.get("/", response_model=List[TimetableBase])
def get_all_timetables(db: Session = Depends(get_db)):
    """
    Get all timetables.
    """
    return crud_timetables.get_all_timetables(db)

@router.get("/{timetable_id}", response_model=TimetableBase)
def get_timetable(timetable_id: int, db: Session = Depends(get_db)):
    """
    Get a timetable by ID.
    """
    timetable = crud_timetables.get_timetable(db, timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    return timetable

@router.put("/{timetable_id}", response_model=TimetableBase)
def update_timetable(timetable_id: int, updates: TimetableBase, db: Session = Depends(get_db)):
    """
    Update a timetable by ID.
    """
    timetable = crud_timetables.get_timetable(db, timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    updated = crud_timetables.update_timetable(db, timetable, updates.dict())
    return {"message": "Timetable updated successfully", "timetable": updated}

@router.delete("/{timetable_id}", response_model=dict)
def delete_timetable(timetable_id: int, db: Session = Depends(get_db)):
    """
    Delete a timetable by ID.
    """
    timetable = crud_timetables.get_timetable(db, timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    crud_timetables.delete_timetable(db, timetable)
    return {"message": "Timetable deleted successfully"}

@router.post("/generate-layout", response_model=dict)
def generate_layout(data: TimetableInput = Body(...)):
    """
        Generate timetable layout from form data (no DB interaction).
    """
    try:
        layout = generate_timetable_layout(
            start_time_str=data.start_time,
            end_time_str=data.end_time,
            breaks=[br.dict() for br in data.breaks],
            lecture_duration_minutes=data.lecture_duration_minutes,
            lab_duration_minutes=data.lab_duration_minutes,
            working_days=data.working_days,
        )
        return layout
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))