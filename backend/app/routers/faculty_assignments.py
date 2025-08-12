from fastapi import APIRouter, Depends, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.crud import faculty_assignments as faculty_crud

router = APIRouter(prefix="/faculty-assignments", tags=["Faculty Assignments"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/")
def create_faculty_assignment(assignment_data: dict, db: Session = Depends(get_db)):
    """
    Create a new faculty assignment.
    Expects JSON: { "faculty_name": "John Doe", "course_name": "Math 101" }
    """
    return faculty_crud.create_faculty_assignment(db, assignment_data)

@router.get("/")
def get_faculty_and_subjects(db: Session = Depends(get_db)):
    """
    Get all faculty with their assigned subjects.
    """
    return faculty_crud.get_faculty_and_subjects(db)

@router.get("/{faculty_name}")
def get_faculty_and_subjects_by_faculty_name(faculty_name: str, db: Session = Depends(get_db)):
    """
    Get subjects for a specific faculty by name.
    """
    results = faculty_crud.get_faculty_and_subjects_by_faculty_name(db, faculty_name)
    if not results:
        raise HTTPException(status_code=404, detail="Faculty not found or no assignments")
    return [{"faculty_name": r.faculty_name, "course_name": r.course_name} for r in results]

