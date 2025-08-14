from pydantic import BaseModel
from typing import List, Dict, Optional

class FacultyAssignmentBase(BaseModel):
    faculty_name: str
    course_name: str

class FacultyAssignmentConstraints(BaseModel):
    course_name: str
    faculty_name: str
    theory: bool
    practical: bool
    number_of_sublabs: int
    division_names: List[str]
    constraints: Optional[List[Dict]] = None