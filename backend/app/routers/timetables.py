from fastapi import APIRouter, Depends, HTTPException, Query, Body
#from redis.commands.search.query import Query
from sqlalchemy.orm import Session
from typing import List
from app.crud import timetables as crud_timetables
from app.crud import users as crud_users
from app.models.users import User
from app.database import SessionLocal
from app.schemas.timetables import TimetableBase, TimetableInput, TimetableResult
from app.services.layout_service import generate_timetable_layout
from app.services.timetable_service import generate_timetable
from app.dependencies.auth import get_current_user, create_access_token
import uuid
import json

router = APIRouter(prefix="/timetables", tags=["Timetables"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/token")
def generate_token(db: Session = Depends(get_db)):
    """
    Generate a token for anonymous user access
    """
    try:
        # Create a new user without email/password
        user_id = uuid.uuid4()

        # Create user using the CRUD function
        user_data = {"id": user_id}
        db_user = crud_users.create_user(db, user_data)

        # Generate token
        token = create_access_token(str(user_id))

        print(f"Created user: {user_id}")  # Add logging
        print(f"Generated token: {token}")  # Add logging

        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": str(user_id)
        }
    except Exception as e:
        db.rollback()
        print(f"Error creating user: {e}")  # Add logging
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

@router.post("/", response_model=TimetableBase)
def create_timetable(timetable_data: TimetableBase, db: Session = Depends(get_db)):
    """
    Create a new timetable.
    """
    new_timetable = crud_timetables.create_timetable(db, timetable_data.dict())
    return {"message": "Timetable created successfully", "timetable": new_timetable}

@router.get("/", response_model=List[TimetableBase])
def get_all_timetables(db: Session = Depends(get_db)):
    """
    Get all timetables.
    """
    return crud_timetables.get_all_timetables(db)

@router.get("/user", response_model=List[TimetableBase])
def get_timetables_by_user(
        db: Session = Depends(get_db),
        user_id: str = Depends(get_current_user)  # Get user from token
):
    """
    Get all timetables for the current user.
    """
    try:
        print(f"Fetching timetables for user: {user_id}")
        timetables = crud_timetables.get_timetables_by_user(db, user_id=user_id)
        print(f"Found {len(timetables)} timetables for user {user_id}")

        # Convert to list of dictionaries and ensure timetable_json is parsed
        timetable_dicts = []
        for timetable in timetables:
            timetable_dict = {
                "id": timetable.id,
                "department_name": timetable.department_name,
                "semester_number": timetable.semester_number,
                "user_id": str(timetable.user_id),
                "created_at": timetable.created_at.isoformat() if timetable.created_at else None,
                # Ensure timetable_json is properly parsed
                "timetable_json": timetable.timetable_json if isinstance(timetable.timetable_json, dict) else json.loads(timetable.timetable_json)
            }
            timetable_dicts.append(timetable_dict)

        print(f"Timetables data: {timetable_dicts}")
        return timetable_dicts
    except Exception as e:
        print(f"Error in get_timetables_by_user: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/{timetable_id}", response_model=TimetableBase)
def get_timetable(timetable_id: int, db: Session = Depends(get_db)):
    """
    Get a timetable by ID.
    """
    timetable = crud_timetables.get_timetable(db, timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    return timetable

@router.put("/{timetable_id}", response_model=TimetableBase)
def update_timetable(timetable_id: int, updates: TimetableBase, db: Session = Depends(get_db)):
    """
    Update a timetable by ID.
    """
    timetable = crud_timetables.get_timetable(db, timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    updated = crud_timetables.update_timetable(db, timetable, updates.dict())
    return {"message": "Timetable updated successfully", "timetable": updated}

@router.delete("/{timetable_id}", response_model=dict)
def delete_timetable(timetable_id: int, db: Session = Depends(get_db)):
    """
    Delete a timetable by ID.
    """
    timetable = crud_timetables.get_timetable(db, timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    crud_timetables.delete_timetable(db, timetable)
    return {"message": "Timetable deleted successfully"}

@router.post("/generate-layout", response_model=dict)
def generate_layout(data: TimetableInput = Body(...)):
    """
        Generate timetable layout from form data (no DB interaction).
    """
    try:
        layout = generate_timetable_layout(
            start_time_str=data.start_time,
            end_time_str=data.end_time,
            breaks=[br.dict() for br in data.breaks],
            lecture_duration_minutes=data.lecture_duration_minutes,
            lab_duration_minutes=data.lab_duration_minutes,
            working_days=data.working_days,
        )
        return layout
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/generate", response_model=TimetableResult)
def generate_timetable_endpoint(
    department_name: str = Query(..., description="Department name"),
    semester_number: int = Query(..., description="Semester number"),
    persist_to_db: bool = Query(False, description="Persist into DB"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)  # Add user dependency
):
    try:
        out = generate_timetable(
            db=db,
            dept=department_name,
            sem=semester_number,
            user_id=user_id,  # Pass user_id to associate with timetable
            persist_to_db=persist_to_db
        )
        return TimetableResult(message="Timetable Generated", **out)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {str(e)}"
        )