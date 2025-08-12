from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.crud import departments as dept_crud

router = APIRouter(prefix="/departments", tags=["Departments"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=dict)
def add_department(name: str, db: Session = Depends(get_db)):
    existing = dept_crud.get_department(db, name)

    if existing:
        raise HTTPException(status_code=400, detail="Department already exists")

    department = dept_crud.create_department(db, name)
    return {"message": "Department created successfully", "department": department.name}

@router.get("/", response_model=list[dict])
def list_departments(db: Session = Depends(get_db)):
    departments = dept_crud.get_all_departments(db)
    return [{"department": dept.name} for dept in departments]