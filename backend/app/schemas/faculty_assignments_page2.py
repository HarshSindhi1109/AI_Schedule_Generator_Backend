from pydantic import BaseModel
from typing import Optional, List

class FacultyAssignmentCourse(BaseModel):
    course_code: str
    faculty_name: str
    theory: bool = False
    practical: bool = False
    number_of_sublabs: Optional[int] = 0
    division_names: Optional[List[str]] = []
    constraints: Optional[List[str]] = []

    class Config:
        orm_mode = True