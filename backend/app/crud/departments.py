from app.models.departments import Department
from sqlalchemy.orm import Session

def create_department(db: Session, name: str):
    dept = Department(name=name)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept

def get_all_departments(db: Session):
    return db.query(Department).all()

def get_department(db: Session, name: str):
    return db.query(Department).filter_by(name=name).first()

# I am not writing code for update and delete operation as I dont think I need those
# operations for the Department class.