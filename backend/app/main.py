from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.core.security import utcnow
from app.db.seed import seed_initial_admin
from app.db.session import SessionLocal, create_tables
from app.schemas.common import HealthResponse
from app.services.face_cache import face_cache
from app.services.face_engine import build_face_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_tables:
        await create_tables()
    async with SessionLocal() as db:
        await seed_initial_admin(db)
    engine, engine_status = build_face_engine()
    app.state.face_engine = engine
    app.state.face_engine_status = engine_status
    async with SessionLocal() as db:
        try:
            await face_cache.refresh(db)
        except Exception:
            if settings.is_production:
                raise
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Code", "X-Device-Key"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/api/health", response_model=HealthResponse, tags=["系统"])
async def health():
    database_status = "ok"
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"
    return HealthResponse(
        status="ok" if database_status == "ok" else "degraded",
        database=database_status,
        face_engine=app.state.face_engine_status,
        time=utcnow(),
    )


@app.get("/", include_in_schema=False)
async def root():
    return {"name": settings.app_name, "docs": "/api/docs", "health": "/api/health"}
