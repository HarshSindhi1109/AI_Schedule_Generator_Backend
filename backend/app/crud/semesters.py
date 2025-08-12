from sqlalchemy.orm import Session
from app.models.semesters import Semester

def create_semester(db: Session, semester_data: dict):
    semester = Semester(**semester_data)
    db.add(semester)
    db.commit()
    db.refresh(semester)
    return semester

def get_all_semesters(db: Session):
    results = db.query(
        Semester.department_name,
        Semester.semester_number
    ).all()

    return [
        {"department_name": r.department_name, "semester_number": r.semester_number} for r in results
    ]

def get_semesters_by_department(db: Session, department_name: str):
    results = (
        db.query(Semester.department_name, Semester.semester_number)
        .filter(Semester.department_name == department_name)
        .all()
    )

    return [
        {"department_name": r.department_name, "semester_number": r.semester_number}
        for r in results
    ]

def update_semester(db: Session, semester, updates: dict):
    for key, value in updates.items():
        setattr(semester, key, value)
    db.commit()
    db.refresh(semester)
    return semester

def delete_semester(db: Session, semester):
    db.delete(semester)
    db.commit()