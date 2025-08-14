from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class UserBase(BaseModel):
    id: UUID
    created_at: datetime

    class Config:
        orm_mode = True