from sqlalchemy import Column, String, Integer, ForeignKeyConstraint
from sqlalchemy.orm import relationship
from ..database import Base

class FacultyAssignment(Base):
    __tablename__ = "faculty_assignments"

    faculty_name = Column(String(100), primary_key=True)
    course_name = Column(String(200), nullable=False)
    course_code = Column(String(50), primary_key=True)
    semester_number = Column(Integer, primary_key=True)
    department_name = Column(String(100), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["department_name", "semester_number", "course_code"],
            ["courses.department_name", "courses.semester_number", "courses.course_code"],
            ondelete="CASCADE",
        ),
    )

    course = relationship("Course", back_populates="faculty_assignments")