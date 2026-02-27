"""FastAPI application for the Competitor Monitoring Dashboard."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add the existing scripts directory so we can import db & models directly
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills", "competitor-monitoring", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import db  # noqa: E402

from api.routers import alerts, analyses, changes, competitors, dashboard, news, partnerships, scan, sources  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.ensure_indexes()
    yield
    db.close()


app = FastAPI(
    title="Competitor Monitoring Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(dashboard.router, prefix="/api")
app.include_router(competitors.router, prefix="/api")
app.include_router(sources.router, prefix="/api")
app.include_router(changes.router, prefix="/api")
app.include_router(analyses.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(partnerships.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(scan.router, prefix="/api")

# Serve React build in production (if frontend/dist exists)
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="spa")
