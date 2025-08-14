from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.crud import courses as crud_courses
from typing import List
from app.schemas.courses import CourseBase

router = APIRouter(prefix="/courses", tags=["courses"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=CourseBase)
def add_course(course_data: CourseBase, db: Session = Depends(get_db)):
    """
        Create a new course.
        course_data should include:
        department_name, semester_number, code, name, t_hrs, tu_hrs, p_hrs, credits
    """
    course = crud_courses.create_course(db, course_data.dict())
    return {
        "message": "Course created successfully",
        "course_code": course.course_code,
        "course_name": course.course_name,
        "semester_number": course.semester_number,
        "department_name": course.department_name,
        "t_hrs": course.t_hrs,
        "tu_hrs": course.tu_hrs,
        "p_hrs": course.p_hrs,
        "credits": course.credits
    }

@router.get("/", response_model=List[CourseBase])
def list_courses(db: Session = Depends(get_db)):
    """
        List all courses.
    """
    courses = crud_courses.get_all_courses(db)
    return [
        {
            "department_name": c.department_name,
            "semester_number": c.semester_number,
            "course_code": c.course_code,
            "course_name": c.course_name,
            "t_hrs": c.t_hrs,
            "tu_hrs": c.tu_hrs,
            "p_hrs": c.p_hrs,
            "credits": c.credits
        }
        for c in courses
    ]

@router.get("/{course_name}", response_model=List[CourseBase])
def get_course_by_name(course_name: str, db: Session = Depends(get_db)):
    """
        Get course(s) by partial or full name match.
        Returns department, semester, code, name, T/Tu/P hours, credits.
    """
    results = crud_courses.get_course_by_name(db, course_name)
    if not results:
        raise HTTPException(status_code=404, detail="Course not found")

    return [
        {
            "department": r.department,
            "semester": r.semester,
            "course_code": r.course_code,
            "course_name": r.course_name,
            "t_hrs": r.t_hrs,
            "tu_hrs": r.tu_hrs,
            "p_hrs": r.p_hrs,
            "credits": r.credits
        }
        for r in results
    ]

@router.put("/{course_code}", response_model=CourseBase)
def edit_course(course_code: str, updates: CourseBase, db: Session = Depends(get_db)):
    """
        Update a course by course_code.
    """
    course = db.query(crud_courses.Course).filter_by(course_code=course_code).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    updated_course = crud_courses.update_course(db, course_code, updates.dict(exclude_unset=True))
    return {"message": "Course updated successfully", "course_code": updated_course.course_code}

@router.delete("/{course_code}", response_model=dict)
def remove_course(course_code: str, db: Session = Depends(get_db)):
    """
        Delete a course by course_code.
    """
    course = db.query(crud_courses.Course).filter_by(course_code=course_code).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    crud_courses.delete_course(db, course_code)
    return {"message": "Course deleted successfully"}