from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.db.mongo import close, ping
from app.api import auth, learning, admin, ai

settings=get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close()

app=FastAPI(title="Smart Learning Lab API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(learning.router)
app.include_router(admin.router)
app.include_router(ai.router)

@app.get("/")
def root(): return {"name":"Smart Learning Lab API","version":"2.0.0","docs":"/docs"}
@app.get("/health")
def health(): return {"status":"ok","mongodb":ping()}
