"""
============================================================
REGENESIS
Development Server
============================================================

Uvicorn entry point for the Regenesis FastAPI backend.

The application itself lives in api.py.
"""

from __future__ import annotations

import uvicorn


def main() -> None:
    """
    Start the Regenesis development server.
    """

    uvicorn.run(
        "backend.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()