import time
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api import admin, ai, auth, learning, growth, advanced, features, media, bulk
from app.core.config import get_settings
from app.core.logging_config import setup_logging, get_logger
from app.db.mongo import close, ping

setup_logging()
logger = get_logger("smart_learning_lab.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("APPLICATION_START | version=4.1.0 | environment=%s", "local/default")
    try:
        ping()
        logger.info("MONGODB_CONNECTED | ping=ok")
    except Exception:
        logger.exception("MONGODB_CONNECTION_FAILED")
        raise

    yield

    logger.info("APPLICATION_SHUTDOWN")
    close()
    logger.info("MONGODB_CONNECTION_CLOSED")


app = FastAPI(
    title="Smart Learning Lab API",
    version="4.1.0",
    description="Complete Smart Learning Lab backend with API request/response logging",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_request_logger(request: Request, call_next):
    """Log every API request and response without exposing passwords/tokens."""
    request_id = uuid.uuid4().hex[:12]
    start = time.perf_counter()

    request.state.request_id = request_id
    path = request.url.path
    query = request.url.query

    logger.info(
        "API_REQUEST | id=%s | method=%s | path=%s%s | client=%s",
        request_id,
        request.method,
        path,
        f"?{query}" if query else "",
        request.client.host if request.client else "unknown",
    )

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "API_EXCEPTION | id=%s | method=%s | path=%s | duration_ms=%.2f",
            request_id,
            request.method,
            path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id

    logger.info(
        "API_RESPONSE | id=%s | method=%s | path=%s | status=%s | duration_ms=%.2f",
        request_id,
        request.method,
        path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        "UNHANDLED_EXCEPTION | id=%s | method=%s | path=%s | error_type=%s",
        request_id,
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


app.include_router(auth.router)
app.include_router(learning.router)
app.include_router(admin.router)
app.include_router(ai.router)
app.include_router(growth.router)
app.include_router(advanced.router)
app.include_router(features.router)
app.include_router(media.router)
app.include_router(bulk.router)


@app.get("/")
def root():
    logger.info("ROOT_ENDPOINT")
    return {"name": "Smart Learning Lab API", "version": "4.1.0", "docs": "/docs"}


@app.get("/health")
def health():
    logger.info("HEALTH_CHECK_START")
    result = ping()
    logger.info("HEALTH_CHECK_RESULT | mongodb=%s", result)
    return {"status": "ok", "mongodb": result}
