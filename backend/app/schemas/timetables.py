from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Any, Optional, List


class TimetableBase(BaseModel):
    id: int
    department_name: str
    semester_number: int
    user_id: UUID
    timetable_json: Any
    created_at: datetime

    class Config:
        orm_mode = True

class BreakInput(BaseModel):
    start: str
    end: str
    name: Optional[str] = "Break"

class TimetableInput(BaseModel):
    department_name: str
    semester_number: int
    start_time: str
    end_time: str
    breaks: List[BreakInput]
    lecture_duration_minutes: int
    lab_duration_minutes: int
    working_days: Optional[List[str]] = None
