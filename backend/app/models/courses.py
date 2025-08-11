from sqlalchemy import Column, String, Integer, ForeignKeyConstraint
from sqlalchemy.orm import relationship
from ..database import Base

class Course(Base):
    __tablename__ = "courses"

    department_name = Column(String(100), primary_key=True)
    semester_number = Column(Integer, primary_key=True)
    course_code = Column(String(50), primary_key=True)
    course_name = Column(String(200), nullable=False)
    t_hrs = Column(Integer, default=0)
    tu_hrs = Column(Integer, default=0)
    p_hrs = Column(Integer, default=0)
    credits = Column(Integer, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["department_name", "semester_number"],
            ["semesters.department_name", "semesters.semester_number"],
            ondelete="CASCADE",
        ),
    )

    semester = relationship("Semester", back_populates="courses")
    faculty_assignment = relationship("FacultyAssignment", back_populates="course")