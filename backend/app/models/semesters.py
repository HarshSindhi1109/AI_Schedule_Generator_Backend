from sqlalchemy import Column, Integer, String, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from ..database import Base

class Semester(Base):
    __tablename__ = "semesters"

    department_name = Column(String(100), ForeignKey("departments.name", ondelete="CASCADE"), primary_key=True)
    semester_number = Column(Integer, primary_key=True)

    __table_args__ = (
        CheckConstraint("semester_number >= 1 AND semester_number <= 8", name="check_sem_number"),
    )

    department = relationship("Department", back_populates="semesters")
    courses = relationship("Course", back_populates="semester")
    timetables = relationship("Timetable", back_populates="semester")