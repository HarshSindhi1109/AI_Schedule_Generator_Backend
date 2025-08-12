from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.crud import users as crud_users
from app.database import SessionLocal
from app.models.users import User

router = APIRouter(prefix="/users", tags=["Users"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=dict)
def create_user(user_data: dict, db: Session = Depends(get_db)):
    """
    Create a new user.
    """
    new_user = crud_users.create_user(db, user_data)
    return {"message": "User created successfully", "user": new_user}

@router.get("/", response_model=List[User])
def get_all_users(db: Session = Depends(get_db)):
    """
    Get all users.
    """
    return crud_users.get_all_users(db)

@router.get("/{user_id}", response_model=User)
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    """
    Get a user by ID.
    """
    user = crud_users.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=dict)
def update_user(user_id: UUID, updates: dict, db: Session = Depends(get_db)):
    """
    Update a user by ID.
    """
    user = crud_users.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updated_user = crud_users.update_user(db, user, updates)
    return {"message": "User updated successfully", "user": updated_user}

@router.delete("/{user_id}", response_model=dict)
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    """
    Delete a user by ID.
    """
    user = crud_users.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    crud_users.delete_user(db, user)
    return {"message": "User deleted successfully"}
