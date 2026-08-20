from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.db.mongo import ping, close
from app.routers import auth, content, admin, personal, ai

settings=get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close()

app=FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False if settings.cors_origin_list == ["*"] else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix=settings.api_prefix
app.include_router(auth.router, prefix=prefix)
app.include_router(content.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)
app.include_router(personal.router, prefix=prefix)
app.include_router(ai.router, prefix=prefix)

@app.get("/")
def root():
    return {"name":settings.app_name,"status":"ok","database":"smart_learning_lab"}

@app.get("/health")
def health():
    return {"status":"ok","mongodb":ping()}
