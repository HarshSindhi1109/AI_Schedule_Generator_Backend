from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.database import SessionLocal
from app.services.excel_service import extract_courses_from_excel
from app.services.layout_service import generate_timetable_layout
from app.crud.courses import create_course
from app.crud import departments as dept_crud
from app.crud import semesters as sem_crud
import json
import redis  # <-- New import

router = APIRouter(prefix="/excel", tags=["Excel Upload"])

# Connect to Redis
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/upload")
async def upload_excel(
    department_name: str = Form(...),
    semester_number: int = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    no_of_breaks: int = Form(...),
    break_start_times: List[str] = Form([]),
    break_end_times: List[str] = Form([]),
    minutes_per_lecture: int = Form(...),
    minutes_per_lab: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # 1. Store department if not exists
        dept = dept_crud.get_department(db, department_name)
        if not dept:
            dept = dept_crud.create_department(db, department_name)

        # 2. Store semester if not exists
        existing_semesters = sem_crud.get_semesters_by_department(db, department_name)
        if not any(s["semester_number"] == semester_number for s in existing_semesters):
            sem_crud.create_semester(db, {
                "department_name": department_name,
                "semester_number": semester_number
            })

        # 3. Dynamically build breaks list
        breaks = []
        for i in range(no_of_breaks):
            if i < len(break_start_times) and i < len(break_end_times):
                breaks.append({
                    "start": break_start_times[i],
                    "end": break_end_times[i],
                    "name": f"Break {i + 1}"
                })

        # 4. Save timetable settings to Redis
        timetable_settings = {
            "start_time": start_time,
            "end_time": end_time,
            "no_of_breaks": no_of_breaks,
            "break_start_times": break_start_times,
            "break_end_times": break_end_times,
            "minutes_per_lecture": minutes_per_lecture,
            "minutes_per_lab": minutes_per_lab
        }
        redis_client.set("timetable_settings", json.dumps(timetable_settings))

        # 5. Store courses
        file_bytes = await file.read()
        courses = extract_courses_from_excel(file_bytes)
        for course in courses:
            course["department_name"] = department_name
            course["semester_number"] = semester_number
            create_course(db, course)

        db.commit()

        # 6. Run layout service with stored variables
        timetable_layout = generate_timetable_layout(
            start_time_str=start_time,
            end_time_str=end_time,
            breaks=breaks,
            lecture_duration_minutes=minutes_per_lecture,
            lab_duration_minutes=minutes_per_lab
        )

        # NEW: Store layout in Redis
        redis_client.set("timetable_layout", json.dumps(timetable_layout))

        return {
            "message": "Data stored in DB & Redis, timetable layout generated",
            "total_courses": len(courses),
            "timetable_layout": timetable_layout
        }

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
