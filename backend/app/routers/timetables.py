from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from app.crud import timetables as crud_timetables
from app.database import SessionLocal
from app.models.timetables import Timetable

router = APIRouter(prefix="/timetables", tags=["Timetables"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=dict)
def create_timetable(timetable_data: dict, db: Session = Depends(get_db)):
    """
    Create a new timetable.
    """
    new_timetable = crud_timetables.create_timetable(db, timetable_data)
    return {"message": "Timetable created successfully", "timetable": new_timetable}

@router.get("/", response_model=List[Timetable])
def get_all_timetables(db: Session = Depends(get_db)):
    """
    Get all timetables.
    """
    return crud_timetables.get_all_timetables(db)

@router.get("/{timetable_id}", response_model=Timetable)
def get_timetable(timetable_id: int, db: Session = Depends(get_db)):
    """
    Get a timetable by ID.
    """
    timetable = crud_timetables.get_timetable(db, timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    return timetable

@router.put("/{timetable_id}", response_model=dict)
def update_timetable(timetable_id: int, updates: dict, db: Session = Depends(get_db)):
    """
    Update a timetable by ID.
    """
    timetable = crud_timetables.get_timetable(db, timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    updated = crud_timetables.update_timetable(db, timetable, updates)
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