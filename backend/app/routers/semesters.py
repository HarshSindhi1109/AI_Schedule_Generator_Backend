from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.crud import semesters as crud_semesters
from typing import List
from app.schemas.semesters import SemesterBase

router = APIRouter(prefix="/semesters", tags=["Semesters"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=SemesterBase)
def create_semester(semester_data: SemesterBase, db: Session = Depends(get_db)):
    """
    Create a new semester.
    Expects JSON: { "department_name": "B.Tech IT", "semester_number": 6 }
    """
    return crud_semesters.create_semester(db, semester_data.dict())


@router.get("/", response_model=List[SemesterBase])
def get_all_semesters(db: Session = Depends(get_db)):
    """
    Get all semesters.
    """
    return crud_semesters.get_all_semesters(db)

@router.get("/{department_name}", response_model=SemesterBase)
def get_semesters_by_department(department_name: str, db: Session = Depends(get_db)):
    """
    Get all semesters for a specific department.
    """
    semesters = crud_semesters.get_semesters_by_department(db, department_name)
    if not semesters:
        raise HTTPException(status_code=404, detail="No semesters found for this department")
    return semesters