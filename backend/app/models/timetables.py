from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class Timetable(Base):
    __tablename__ = "timetables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    department_name = Column(String, nullable=False)
    semester_number = Column(Integer, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    timetable_json = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["department_name", "semester_number"],
            ["semesters.department_name", "semesters.semester_number"],
            ondelete="CASCADE",
        ),
    )

    user = relationship("User", back_populates="timetables")
    semester = relationship("Semester", back_populates="timetables")
