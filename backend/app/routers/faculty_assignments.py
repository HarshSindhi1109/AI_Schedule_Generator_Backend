from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.schemas.faculty_assignments import (
    FacultyAssignmentBase,
    FacultyAssignmentConstraints,
    FacultyAssignmentsRequest
)
from app.crud.faculty_assignments import create_faculty_assignment, get_course_by_name
from app.utils.redis_client import (
    store_assignment_constraints,
    generate_redis_key,
    get_redis
)
from typing import List
from app.services.constraint_service import get_assignment_constraints
from app.services.timetable_service import generate_timetable
from uuid import UUID
import json
import logging
from app.dependencies.auth import get_current_user

logger = logging.getLogger(__name__)  # Add this for logging

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
def create_faculty_assignments_with_constraints(
        request: FacultyAssignmentsRequest,
        department_name: str = Query(..., alias="department_name"),
        semester_number: int = Query(..., alias="semester_number"),
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user)
):
    """
    Create faculty assignments with constraints stored in Redis,
    then return generated timetable.
    """
    results = []
    errors = []
    consolidated_assignments = []  # For storing assignments in timetable format

    for assignment in request.assignments:
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

        # 3. Prepare constraints data (using global request fields)
        constraints_data = {
            "theory": assignment.theory,
            "practical": assignment.practical,
            "number_of_sublabs": request.number_of_sublabs,
            "division_names": request.division_names,
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

            # Add to consolidated assignments list for timetable service
            consolidated_assignments.append({
                "course_name": assignment.course_name,
                "faculty_name": assignment.faculty_name,
                "theory": assignment.theory,
                "practical": assignment.practical,
                "number_of_sublabs": request.number_of_sublabs,
                "division_names": request.division_names,
                "constraints": assignment.constraints or []
            })
        except Exception as e:
            errors.append(f"Redis storage failed for {assignment.course_name}: {str(e)}")
            db.delete(db_assignment)
            db.commit()

    # 5. Store consolidated assignments in Redis for timetable service
    if consolidated_assignments:
        r = get_redis()
        rkey = f"tt:{department_name}:{semester_number}:faculty"
        try:
            r.set(rkey, json.dumps(consolidated_assignments))
            logger.info(f"Stored consolidated assignments in Redis: {rkey}")
        except Exception as e:
            errors.append(f"Failed to store consolidated assignments: {str(e)}")
    else:
        errors.append("No valid assignments to consolidate")

    if errors:
        return {
            "success": False,
            "message": "Completed with errors",
            "results": results,
            "errors": errors
        }

    # Generate timetable
    try:
        timetable_output = generate_timetable(
            db=db,
            dept=department_name,
            sem=semester_number,
            user_id=user_id,
            persist_to_db=True
        )
    except Exception as e:
        # Log the full error for debugging
        logger.error(f"Timetable generation failed: {str(e)}", exc_info=True)

        # Return a more informative error message
        error_detail = f"Timetable generation failed: {str(e)}"
        if "conflicts" in str(e).lower():
            error_detail += ". There were too many scheduling conflicts. Please adjust your constraints and try again."

        raise HTTPException(status_code=500, detail=error_detail)

    # 6. Extract layout information from Redis
    r = get_redis()
    rkey_layout = f"tt:{department_name}:{semester_number}:layout"

    try:
        layout_data = json.loads(r.get(rkey_layout) or "{}")
        layout = layout_data.get("layout", {})

        # Extract start_time and end_time from time_slots
        time_slots = layout.get("time_slots", [])
        start_time = None
        end_time = None

        if time_slots:
            # Sort time slots to get the earliest start and latest end
            sorted_slots = sorted(time_slots, key=lambda x: x.get("start", ""))
            start_time = sorted_slots[0].get("start") if sorted_slots else None
            end_time = sorted_slots[-1].get("end") if sorted_slots else None

        # FIXED: Extract breaks from layout instead of grid, and use proper structure
        breaks = []

        # First try to get breaks from layout configuration
        if layout.get("breaks"):
            for break_item in layout.get("breaks", []):
                if break_item.get("start_time") and break_item.get("end_time"):
                    breaks.append({
                        "start_time": break_item["start_time"],
                        "end_time": break_item["end_time"],
                        "name": break_item.get("name", "Break")
                    })

        # Fallback: Extract breaks from grid if not found in layout
        if not breaks:
            grid = layout_data.get("grid", {})
            break_intervals = set()  # Use set to avoid duplicates

            for day, day_schedule in grid.items():
                if not isinstance(day_schedule, dict):
                    continue

                for time_slot, activities in day_schedule.items():
                    if activities and isinstance(activities, (list, dict)):
                        # Handle both list and single dict formats
                        activities_list = activities if isinstance(activities, list) else [activities]

                        for activity in activities_list:
                            if isinstance(activity, dict) and activity.get("type") in ("break", "Break"):
                                # Extract time slot components
                                if '-' in time_slot:
                                    start, end = time_slot.split('-')
                                    break_intervals.add((start, end))

            # Convert unique break intervals to proper format
            for start, end in break_intervals:
                breaks.append({
                    "start_time": start,
                    "end_time": end,
                    "name": "Break"
                })

        # FIXED: Change slot_duration to minutes_per_lecture to match frontend expectation
        slot_duration = layout.get("slot_duration", 55)
        lab_minutes = layout.get("lab_minutes", 110)

        config = {
            "start_time": start_time or "07:30",
            "end_time": end_time or "13:40",
            "minutes_per_lecture": slot_duration,  # FIXED: Changed key name
            "lab_minutes": lab_minutes,
            "breaks": breaks
        }

    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        logger.error(f"Failed to extract layout information: {str(e)}")
        # Provide default config if layout extraction fails
        config = {
            "start_time": "07:30",
            "end_time": "13:40",
            "minutes_per_lecture": 55,
            "lab_minutes": 110,
            "breaks": []
        }

    # FIXED: Return proper structure with grid and config at top level
    # Extract grid from timetable_output and combine with config
    if isinstance(timetable_output, dict) and 'grid' in timetable_output:
        grid_data = timetable_output['grid']
    else:
        grid_data = timetable_output

    return {
        "grid": grid_data,
        "config": config
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