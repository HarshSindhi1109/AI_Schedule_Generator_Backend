from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.crud import semesters as crud_semesters

router = APIRouter(prefix="/semesters", tags=["Semesters"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/")
def create_semester(semester_data: dict, db: Session = Depends(get_db)):
    """
    Create a new semester.
    Expects JSON: { "department_name": "B.Tech IT", "semester_number": 6 }
    """
    return crud_semesters.create_semester(db, semester_data)


@router.get("/")
def get_all_semesters(db: Session = Depends(get_db)):
    """
    Get all semesters.
    """
    return crud_semesters.get_all_semesters(db)

@router.get("/{department_name}")
def get_semesters_by_department(department_name: str, db: Session = Depends(get_db)):
    """
    Get all semesters for a specific department.
    """
    semesters = crud_semesters.get_semesters_by_department(db, department_name)
    if not semesters:
        raise HTTPException(status_code=404, detail="No semesters found for this department")
    return semesters