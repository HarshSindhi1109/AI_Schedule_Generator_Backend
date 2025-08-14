from pydantic import BaseModel

class DepartmentBase(BaseModel):
    name: str

    class Config:
        orm_mode = True