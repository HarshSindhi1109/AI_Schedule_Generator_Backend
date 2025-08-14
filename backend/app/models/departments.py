from sqlalchemy import Column, String
from ..database import Base
from sqlalchemy.orm import relationship

class Department(Base):
    __tablename__ = "departments"
    name = Column(String(100), primary_key=True)

    semesters = relationship("Semester", back_populates="department")