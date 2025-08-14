from pydantic import BaseModel

class SemesterBase(BaseModel):
    department_name: str
    semester_number: int

    class Config:
        orm_mode = True