from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.courses import Course
from app.models.semesters import Semester
from app.models.departments import Department
from typing import List

def create_course(db: Session, course_data: dict):
    course = Course(**course_data)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course

def get_all_courses(db: Session):
    return db.query(Course).all()

def get_course_by_name(db: Session, course_name: str):
    stmt = (
        select(
            Department.name.label("department"),
            Semester.semester_number.label("semester"),
            Course.course_code,
            Course.course_name,
            Course.t_hrs,
            Course.tu_hrs,
            Course.p_hrs,
            Course.credits
        )
        .join(Semester, Course.semester_number == Semester.semester_number)
        .join(Department, Semester.department_name == Department.name)
        .where(Course.course_name.ilike(f"%{course_name}%"))
    )

    results = db.execute(stmt).all()
    return results

def get_courses_for_department_semester(
    db: Session,
    department_name: str,
    semester_number: int
) -> List[Course]:
    return (
        db.query(Course)
        .join(Semester)
        .join(Department)
        .filter(
            Department.name == department_name,
            Semester.semester_number == semester_number
        )
        .all()
    )

def update_course(db: Session, course, updates: dict):
    for key, value in updates.items():
        setattr(course, key, value)

    db.commit()
    db.refresh(course)
    return course

def delete_course(db: Session, course):
    db.delete(course)
    db.commit()