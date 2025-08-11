from sqlalchemy import Column, String
from ..database import Base

class Department(Base):
    __tablename__ = "departments"
    name = Column(String(100), primary_key=True)