from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    id: Optional[UUID] = None

class UserBase(BaseModel):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True