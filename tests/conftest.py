"""
Pytest configuration and shared fixtures.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure root of project is on path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Force mock mode for all tests
os.environ.setdefault("SAP_USE_MOCK", "true")
os.environ.setdefault("OPENAI_API_KEY", "sk-dummy-key-for-testing")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///./test.db")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
