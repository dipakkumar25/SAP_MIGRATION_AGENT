"""
Integration tests for the FastAPI REST endpoints.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.api.app import create_app

app = create_app()


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest.fixture
def sap_payload():
    return {"system_id": "ECC", "host": "localhost", "client": "100"}


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data


# ─────────────────────────────────────────────────────────────────────────────
# Inventory
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inventory_endpoint(client, sap_payload, monkeypatch):
    monkeypatch.setenv("SAP_USE_MOCK", "true")
    resp = await client.post("/api/v1/inventory", json=sap_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "system_id" in data
    assert data["system_id"] == "ECC"
    assert "sap_version" in data


# ─────────────────────────────────────────────────────────────────────────────
# Custom Code
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_custom_code_endpoint(client, sap_payload, monkeypatch):
    monkeypatch.setenv("SAP_USE_MOCK", "true")
    resp = await client.post("/api/v1/custom-code", json=sap_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_objects" in data
    assert data["total_objects"] > 0
    assert "z_programs" in data


# ─────────────────────────────────────────────────────────────────────────────
# ATC
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_atc_endpoint(client, sap_payload, monkeypatch):
    monkeypatch.setenv("SAP_USE_MOCK", "true")
    resp = await client.post("/api/v1/atc", json=sap_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_findings" in data
    assert data["total_findings"] > 0
    assert "critical_count" in data


# ─────────────────────────────────────────────────────────────────────────────
# Risk
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_risk_endpoint(client, sap_payload, monkeypatch, tmp_path):
    monkeypatch.setenv("SAP_USE_MOCK", "true")
    monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
    resp = await client.post("/api/v1/risk", json=sap_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "overall_score" in data
    assert 0 <= data["overall_score"] <= 100
    assert "risk_level" in data


# ─────────────────────────────────────────────────────────────────────────────
# Start Assessment (async)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_assessment(client, sap_payload, monkeypatch):
    monkeypatch.setenv("SAP_USE_MOCK", "true")
    resp = await client.post("/api/v1/assess", json=sap_payload)
    assert resp.status_code == 202
    data = resp.json()
    assert "assessment_id" in data
    assert data["status"] == "queued"


# ─────────────────────────────────────────────────────────────────────────────
# 404 for missing assessment
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_not_found(client):
    resp = await client.get("/api/v1/status/non-existent-id")
    assert resp.status_code == 404
