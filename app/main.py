from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import ping_database, close_database
from app.routers import auth,content,student,admin,health

@asynccontextmanager
async def lifespan(app):
    ping_database()
    yield
    close_database()

app=FastAPI(title="Smart Learning Lab API",description="MongoDB-backed learning API",version="3.1.0",lifespan=lifespan)
origins=["*"] if settings.cors_origins=="*" else [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=False,allow_methods=["*"],allow_headers=["*"])
app.include_router(auth.router,prefix="/api/auth",tags=["Authentication"])
app.include_router(content.router,prefix="/api",tags=["Learning Content"])
app.include_router(student.router,prefix="/api",tags=["Student"])
app.include_router(admin.router,prefix="/api/admin",tags=["Admin"])
app.include_router(health.router,prefix="/api",tags=["Health"])

@app.get("/")
def root():
    return {"status":"success","app":"Smart Learning Lab","version":"3.1.0","database":"MongoDB"}
