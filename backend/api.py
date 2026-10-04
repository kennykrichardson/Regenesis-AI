"""
============================================================
REGENESIS
FastAPI Application
============================================================

Application entry point for the Regenesis backend.

Responsibilities:
    - Create the FastAPI application
    - Configure CORS for the local frontend
    - Register API routes
    - Configure API metadata

Business logic lives elsewhere.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import router


# ============================================================
# Configuration
# ============================================================

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def get_cors_origins() -> list[str]:
    """
    Return configured CORS origins.

    REGENESIS_CORS_ORIGINS may contain a comma-separated list
    of additional frontend origins.
    """

    configured_origins = os.getenv("REGENESIS_CORS_ORIGINS")

    if not configured_origins:
        return DEFAULT_CORS_ORIGINS

    return [
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    ]


# ============================================================
# Application
# ============================================================

app = FastAPI(
    title="Regenesis",
    description=(
        "Deterministic GitHub source-to-prompt reconstruction "
        "engine."
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Routes
# ============================================================

app.include_router(router)


# ============================================================
# Root
# ============================================================

@app.get("/")
def root() -> dict[str, str]:
    """
    Basic API information endpoint.
    """

    return {
        "name": "Regenesis",
        "version": "1.0.0",
        "status": "running",
    }


__all__ = [
    "app",
]