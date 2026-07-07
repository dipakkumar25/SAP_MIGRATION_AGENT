"""
Application entry point.
Run with: uvicorn main:app --reload
"""
from __future__ import annotations

import uvicorn

from app.api.app import create_app
from app.services.logger import configure_logging

configure_logging()
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
