from pydantic import BaseModel

class CourseBase(BaseModel):
    department_name: str
    semester_number: int
    course_code: str
    course_name: str
    t_hrs: int
    tu_hrs: int
    p_hrs: int
    credits: int

    class Config:
        orm_mode = True