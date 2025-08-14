from fastapi import FastAPI
from app.routers import (
    departments,
    semesters,
    users,
    courses,
    faculty_assignments,
    timetables,
    excel
)

app = FastAPI(
    title="Timetable",
    description="API for managing departments, semesters, users, courses, faculty assignments, and timetables.",
    version="1.0.0"
)

app.include_router(departments.router)
app.include_router(semesters.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(faculty_assignments.router)
app.include_router(timetables.router)
app.include_router(excel.router)

@app.get("/")
def root():
    return {"message": "Welcome to Timetable API"}