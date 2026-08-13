from fastapi import FastAPI
from app.database import ping_database
from app.routers import (
    auth, users, courses, subjects, lessons, videos, quizzes,
    progress, bookmarks, achievements, notifications
)

app = FastAPI(
    title="Smart Learning Lab API",
    description="Backend API for the Smart Learning Lab Android application",
    version="1.0.0"
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(courses.router, prefix="/api/courses", tags=["Courses"])
app.include_router(subjects.router, prefix="/api/subjects", tags=["Subjects"])
app.include_router(lessons.router, prefix="/api/lessons", tags=["Lessons"])
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(quizzes.router, prefix="/api/quizzes", tags=["Quizzes"])
app.include_router(progress.router, prefix="/api/progress", tags=["Progress"])
app.include_router(bookmarks.router, prefix="/api/bookmarks", tags=["Bookmarks"])
app.include_router(achievements.router, prefix="/api/achievements", tags=["Achievements"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])

@app.get("/")
def welcome():
    return {"message": "Welcome to Smart Learning Lab API", "status": "success", "version": "1.0.0"}

@app.get("/api/health")
def health():
    try:
        ping_database()
        return {"status": "success", "api": "up", "database": "connected"}
    except Exception as exc:
        return {"status": "error", "api": "up", "database": "disconnected", "detail": str(exc)}
