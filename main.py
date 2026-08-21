from app.api.enterprise import router as enterprise_router
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import admin, ai, auth, learning, growth, advanced, features, innovation
from app.core.config import get_settings
from app.db.mongo import close, ping

settings=get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    ping()
    yield
    close()

app=FastAPI(title="Smart Learning Lab API",version="4.0.0",description="Complete Smart Learning Lab backend",lifespan=lifespan)
app.include_router(enterprise_router)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origin_list,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(auth.router)
app.include_router(learning.router)
app.include_router(admin.router)
app.include_router(ai.router)
app.include_router(growth.router)
app.include_router(advanced.router)
app.include_router(features.router)
app.include_router(innovation.router)

@app.get("/")
def root(): return {"name":"Smart Learning Lab API","version":"4.0.0","docs":"/docs"}

@app.get("/health")
def health(): return {"status":"ok","mongodb":ping()}
