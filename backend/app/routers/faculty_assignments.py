from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.schemas.faculty_assignments import (
    FacultyAssignmentBase,
    FacultyAssignmentConstraints
)
from app.crud.faculty_assignments import create_faculty_assignment, get_course_by_name
from app.utils.redis_client import (
    store_assignment_constraints,
    generate_redis_key
)
from typing import List
from app.services.constraint_service import get_assignment_constraints

router = APIRouter(prefix="/faculty-assignments", tags=["Faculty Assignments"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=FacultyAssignmentBase)
def create_faculty_assignment_endpoint(
        assignment_data: FacultyAssignmentBase,
        db: Session = Depends(get_db)
):
    """Create basic faculty assignment (without constraints)"""
    result = create_faculty_assignment(db, assignment_data.dict())
    if not result:
        raise HTTPException(status_code=400, detail="Duplicate assignment")
    return result


@router.get("/", response_model=FacultyAssignmentBase)
def get_faculty_and_subjects(db: Session = Depends(get_db)):
    """Get all faculty with their assigned subjects"""
    return db.query(models.FacultyAssignment).all()


@router.get("/{faculty_name}", response_model=FacultyAssignmentBase)
def get_faculty_and_subjects_by_name(
        faculty_name: str,
        db: Session = Depends(get_db)
):
    """Get subjects for a specific faculty"""
    results = db.query(models.FacultyAssignment).filter(
        models.FacultyAssignment.faculty_name == faculty_name
    ).all()
    if not results:
        raise HTTPException(status_code=404, detail="Faculty not found")
    return results


@router.post("/with-constraints")
def create_assignment_with_constraints(
        department_name: str,
        semester_number: int,
        assignments: List[FacultyAssignmentConstraints] = Body(...),
        db: Session = Depends(get_db)
):
    """
    Create faculty assignments with constraints stored in Redis
    """
    results = []
    errors = []

    for assignment in assignments:
        # 1. Get course details from database
        course = get_course_by_name(
            db,
            department_name,
            semester_number,
            assignment.course_name
        )

        if not course:
            errors.append(f"Course not found: {assignment.course_name}")
            continue

        # 2. Create base assignment in PostgreSQL
        base_data = {
            "faculty_name": assignment.faculty_name,
            "course_name": assignment.course_name,
            "course_code": course.course_code,
            "semester_number": semester_number,
            "department_name": department_name
        }

        db_assignment = create_faculty_assignment(db, base_data)
        if not db_assignment:
            errors.append(f"Duplicate assignment: {assignment.faculty_name} for {assignment.course_name}")
            continue

        # 3. Prepare constraints data
        constraints_data = {
            "theory": assignment.theory,
            "practical": assignment.practical,
            "number_of_sublabs": assignment.number_of_sublabs,
            "division_names": assignment.division_names,
            "constraints": assignment.constraints or []
        }

        # 4. Store constraints in Redis
        try:
            redis_key = generate_redis_key(
                assignment.faculty_name,
                assignment.course_name
            )
            store_assignment_constraints(redis_key, constraints_data)
            results.append({
                "course": assignment.course_name,
                "faculty": assignment.faculty_name,
                "redis_key": redis_key
            })
        except Exception as e:
            errors.append(f"Redis storage failed for {assignment.course_name}: {str(e)}")
            # Rollback DB assignment if Redis fails
            db.delete(db_assignment)
            db.commit()

    if errors:
        return {
            "success": False,
            "message": "Completed with errors",
            "results": results,
            "errors": errors
        }
    return {
        "success": True,
        "message": "All assignments created successfully",
        "results": results
    }


@router.get("/constraints/{faculty_name}/{course_name}")
def get_assignment_constraints_endpoint(
        faculty_name: str,
        course_name: str,
        db: Session = Depends(get_db)
):
    """Get constraints for a specific assignment"""
    # Generate Redis key
    redis_key = generate_redis_key(faculty_name, course_name)

    # Retrieve from Redis
    constraints = get_assignment_constraints(redis_key)

    if not constraints:
        raise HTTPException(status_code=404, detail="Constraints not found")

    return constraints