from sqlalchemy.orm import Session
from app.models.faculty_assignments import FacultyAssignment
from sqlalchemy.exc import IntegrityError
from app.models.courses import Course

def create_faculty_assignment(db: Session, assignment_data: dict):
    assignmet = FacultyAssignment(**assignment_data)
    db.add(assignmet)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Handle duplicate assignment
        return None
    db.refresh(assignmet)
    return assignmet

def get_faculty_and_subjects(db: Session):
    results = db.query(
        FacultyAssignment.faculty_name,
        FacultyAssignment.course_name
    ).all()

    return [{"faculty_name": r.faculty_name, "course_name": r.course_name} for r in results]

def get_course_by_name(
    db: Session,
    department_name: str,
    semester_number: int,
    course_name: str
):
    """Get course details by name"""
    return db.query(Course).filter(
        Course.department_name == department_name,
        Course.semester_number == semester_number,
        Course.course_name == course_name
    ).first()

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