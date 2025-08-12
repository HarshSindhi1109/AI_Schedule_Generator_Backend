from sqlalchemy.orm import Session
from app.models.faculty_assignments import FacultyAssignment

def create_faculty_assignment(db: Session, assignment_data: dict):
    assignmet = FacultyAssignment(**assignment_data)
    db.add(assignmet)
    db.commit()
    db.refresh(assignmet)
    return assignmet

def get_faculty_and_subjects(db: Session):
    results = db.query(
        FacultyAssignment.faculty_name,
        FacultyAssignment.course_name
    ).all()

    return [{"faculty_name": r.faculty_name, "course_name": r.course_name} for r in results]

def get_faculty_and_subjects_by_faculty_name(db: Session, faculty_name: str):
    return (
        db.query(FacultyAssignment.faculty_name, FacultyAssignment.course_name)
        .filter(FacultyAssignment.faculty_name == faculty_name)
        .all()
    )

def update_faculty_assignment(db: Session, assignment, updates: dict):
    for key, value in updates.items():
        setattr(assignment, key, value)
    db.commit()
    db.refresh(assignment)
    return assignment

def delete_faculty_assignment(db: Session, assignment):
    db.delete(assignment)
    db.commit()