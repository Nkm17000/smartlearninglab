from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.mongo import close, ping
from app.routers import (
    auth, exams, learning, questions, tests, progress,
    current_affairs, personal, notifications, admin, ai
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate MongoDB connectivity when the server starts.
    ping()
    yield
    close()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Smart Learning Lab competitive-exam preparation backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix = settings.api_prefix

app.include_router(auth.router, prefix=prefix)
app.include_router(exams.router, prefix=prefix)
app.include_router(learning.router, prefix=prefix)
app.include_router(questions.router, prefix=prefix)
app.include_router(tests.router, prefix=prefix)
app.include_router(progress.router, prefix=prefix)
app.include_router(current_affairs.router, prefix=prefix)
app.include_router(personal.router, prefix=prefix)
app.include_router(notifications.router, prefix=prefix)
app.include_router(ai.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    try:
        ping()
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "degraded", "database": "disconnected", "error": str(exc)}
