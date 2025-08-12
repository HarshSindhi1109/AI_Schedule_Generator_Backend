from sqlalchemy.orm import Session
from app.models.users import User
from uuid import UUID

def create_user(db: Session, user_data: dict):
    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_all_users(db: Session):
    return db.query(User).all()

def get_user(db: Session, user_id: UUID):
    return db.query(User).filter_by(id=user_id).first()

def update_user(db: Session, user, updates: dict):
    for key, value in updates.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user

def delete_user(db: Session, user):
    db.delete(user)
    db.commit()
