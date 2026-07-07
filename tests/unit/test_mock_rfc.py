"""
Unit tests for the Mock RFC Client.
"""
from __future__ import annotations

import pytest
from app.services.mock_rfc import MockRFCClient


@pytest.fixture
def rfc() -> MockRFCClient:
    return MockRFCClient(ashost="localhost", sysnr="00", client="100",
                         user="TEST", passwd="test", lang="EN")


def test_system_info(rfc):
    result = rfc.call("RFC_SYSTEM_INFO")
    assert "RFCSI_EXPORT" in result
    info = result["RFCSI_EXPORT"]
    assert info["RFCSYSID"] == "ECC"
    assert info["RFCHOST"] == "sapeccprd.company.com"


def test_server_list(rfc):
    result = rfc.call("TH_SERVER_LIST")
    assert "LIST" in result
    assert len(result["LIST"]) > 0


def test_client_list(rfc):
    result = rfc.call("SUSR_GET_ADMIN_USER_LOGIN_INFO")
    assert "CLIENTS" in result
    clients = result["CLIENTS"]
    assert any(c["MANDT"] == "100" for c in clients)


def test_addon_list(rfc):
    result = rfc.call("DELIVERY_GET_PACKAGES")
    packs = result.get("PACKS", [])
    assert len(packs) >= 5
    names = [p["COMPONENT"] for p in packs]
    assert "SAP_BASIS" in names


def test_custom_programs(rfc):
    result = rfc.call("Z_GET_CUSTOM_PROGRAMS")
    progs = result.get("PROGRAMS", [])
    assert len(progs) == 50
    for prog in progs[:5]:
        assert prog["PROGNAME"].startswith("ZCUST_REPORT_")
        assert int(prog["LINES"]) > 0


def test_function_modules(rfc):
    result = rfc.call("Z_GET_FUNCTION_MODULES")
    fms = result.get("FUNCTION_MODULES", [])
    assert len(fms) == 30


def test_classes(rfc):
    result = rfc.call("Z_GET_CLASSES")
    classes = result.get("CLASSES", [])
    assert len(classes) == 20


def test_custom_tables(rfc):
    result = rfc.call("Z_GET_CUSTOM_TABLES")
    tables = result.get("TABLES", [])
    assert len(tables) == 10
    names = [t["TABNAME"] for t in tables]
    assert "ZCUST_HEADER" in names


def test_enhancements(rfc):
    result = rfc.call("Z_GET_ENHANCEMENTS")
    enhancements = result.get("ENHANCEMENTS", [])
    assert len(enhancements) >= 5
    types = {e["TYPE"] for e in enhancements}
    assert "BADI" in types
    assert "USER_EXIT" in types


def test_atc_run_and_results(rfc):
    run = rfc.call("SCI_RUN_CHECK")
    assert run.get("STATUS") == "COMPLETED"
    run_id = run.get("RUN_ID", "")
    results = rfc.call("SCI_GET_RESULTS", RUN_ID=run_id)
    findings = results.get("FINDINGS", [])
    assert len(findings) > 0
    # Verify security findings
    security = [f for f in findings if f["CATEGORY"] == "SECURITY"]
    assert len(security) >= 5


def test_transport_landscape(rfc):
    result = rfc.call("TMS_MGR_GET_LANDSCAPE_INFO")
    systems = result.get("SYSTEMS", [])
    assert len(systems) == 3
    routes = result.get("ROUTES", [])
    assert len(routes) == 2


def test_unknown_fm_raises(rfc):
    with pytest.raises(NotImplementedError):
        rfc.call("NON_EXISTENT_FM_XYZ")


def test_context_manager(rfc):
    with rfc as client:
        result = client.call("RFC_SYSTEM_INFO")
    assert result is not None
