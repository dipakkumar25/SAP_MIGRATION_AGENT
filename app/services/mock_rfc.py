"""
Mock SAP RFC client.

Simulates RFC function module responses so the agent pipeline can run
end-to-end without a live SAP system.  All data matches a realistic
ECC 6.0 EHP8 landscape.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.services.logger import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Mock data generators
# ─────────────────────────────────────────────────────────────────────────────

_OWNERS = ["JOHN_S", "MARIA_K", "DEV_TEAM", "BASIS_ADM", "ABAP_DEV"]
_PACKAGES = ["ZCUSTOM", "ZFIN", "ZMM", "ZSD", "ZHR", "ZUTILS", "ZMIG"]
_TRANSPORT_PREFIX = "ECCK9"

def _rnd_date(days_back: int = 730) -> str:
    d = datetime.utcnow() - timedelta(days=random.randint(0, days_back))
    return d.strftime("%Y%m%d")

def _transport() -> str:
    return f"{_TRANSPORT_PREFIX}{random.randint(100000, 999999)}"


# Module-level dispatch table and decorator — avoids NameError in Python 3.12+
# where the class name is not available inside the class body during decoration.
_RFC_DISPATCH: Dict[str, Any] = {}


def _register(name: str):
    """Register a method as handler for the named RFC function module."""
    def decorator(fn):
        _RFC_DISPATCH[name] = fn
        return fn
    return decorator


class MockRFCClient:
    """Drop-in replacement for pyrfc.Connection."""

    _dispatch = _RFC_DISPATCH

    def __init__(self, **params: Any) -> None:
        self._params = params
        log.info("MockRFCClient initialised", params={k: v for k, v in params.items() if k != "passwd"})

    # ── System info ──────────────────────────────────────────────────────────

    def call(self, func_module: str, **kwargs: Any) -> Dict[str, Any]:
        log.debug("RFC call", func_module=func_module)
        method = self._dispatch.get(func_module)
        if method is None:
            raise NotImplementedError(f"Mock not implemented for: {func_module}")
        return method(self, **kwargs)

    # ── RFC handlers ─────────────────────────────────────────────────────────

    @_register("RFC_SYSTEM_INFO")
    def _system_info(self, **_) -> Dict[str, Any]:
        return {
            "RFCSI_EXPORT": {
                "RFCSYSID": "ECC",
                "RFCHOST": "sapeccprd.company.com",
                "RFCDBHOST": "sapdbprd.company.com",
                "RFCDBSYS": "HDB",
                "RFCSAPRL": "740",
                "RFCKERNRL": "753",
            }
        }

    @_register("TH_SERVER_LIST")
    def _server_list(self, **_) -> Dict[str, Any]:
        return {
            "LIST": [
                {"NAME": "sapeccprd_ECC_00", "HOST": "sapeccprd.company.com", "USERS": 145}
            ]
        }

    @_register("SUSR_GET_ADMIN_USER_LOGIN_INFO")
    def _client_list(self, **_) -> Dict[str, Any]:
        return {
            "CLIENTS": [
                {"MANDT": "100", "MTEXT": "Production", "ORT01": "Frankfurt"},
                {"MANDT": "200", "MTEXT": "Quality", "ORT01": "Frankfurt"},
                {"MANDT": "300", "MTEXT": "Development", "ORT01": "Frankfurt"},
            ]
        }

    @_register("RFC_GET_LOCAL_DESTINATIONS")
    def _rfc_destinations(self, **_) -> Dict[str, Any]:
        dests = []
        for d in ["ECC_QUALITY", "BW_PRD", "CRM_PRD", "PI_PRD", "MDG_PRD"]:
            dests.append({"RFCDEST": d, "RFCTYPE": "3", "RFCHOST": f"{d.lower()}.company.com"})
        return {"DESTINATIONS": dests}

    @_register("DELIVERY_GET_PACKAGES")
    def _addon_list(self, **_) -> Dict[str, Any]:
        return {
            "PACKS": [
                {"COMPONENT": "SAP_BASIS", "RELEASE": "740", "SP_LEVEL": "SP25"},
                {"COMPONENT": "SAP_APPL", "RELEASE": "617", "SP_LEVEL": "SP08"},
                {"COMPONENT": "SAP_HR", "RELEASE": "617", "SP_LEVEL": "SP08"},
                {"COMPONENT": "FINBASIS", "RELEASE": "617", "SP_LEVEL": "SP08"},
                {"COMPONENT": "IS_OIL", "RELEASE": "617", "SP_LEVEL": "SP03"},
            ]
        }

    @_register("DB6_GET_DB_SYSTEM_INFO")
    def _hana_info(self, **_) -> Dict[str, Any]:
        return {"DB_SYSTEM": "SAP HANA", "DB_RELEASE": "2.0 SP07", "DB_HOST": "sapdbprd.company.com"}

    # ── Custom code ──────────────────────────────────────────────────────────

    @_register("Z_GET_CUSTOM_PROGRAMS")
    def _custom_programs(self, **_) -> Dict[str, Any]:
        progs = []
        for i in range(1, 51):
            progs.append({
                "PROGNAME": f"ZCUST_REPORT_{i:03d}",
                "DEVCLASS": random.choice(_PACKAGES),
                "CNAM": random.choice(_OWNERS),
                "UNAM": random.choice(_OWNERS),
                "UDAT": _rnd_date(),
                "LINES": random.randint(50, 3000),
                "TRKORR": _transport(),
            })
        return {"PROGRAMS": progs}

    @_register("Z_GET_FUNCTION_MODULES")
    def _function_modules(self, **_) -> Dict[str, Any]:
        fms = []
        for i in range(1, 31):
            fms.append({
                "FUNCNAME": f"Z_CALC_INVOICE_{i:03d}",
                "DEVCLASS": random.choice(_PACKAGES),
                "CNAM": random.choice(_OWNERS),
                "UDAT": _rnd_date(),
                "LINES": random.randint(30, 800),
                "TRKORR": _transport(),
            })
        return {"FUNCTION_MODULES": fms}

    @_register("Z_GET_CLASSES")
    def _classes(self, **_) -> Dict[str, Any]:
        clazzes = []
        for i in range(1, 21):
            clazzes.append({
                "CLSNAME": f"ZCL_MIGRATION_UTIL_{i:02d}",
                "DEVCLASS": random.choice(_PACKAGES),
                "CNAM": random.choice(_OWNERS),
                "UDAT": _rnd_date(),
                "LINES": random.randint(100, 2000),
                "TRKORR": _transport(),
            })
        return {"CLASSES": clazzes}

    @_register("Z_GET_CUSTOM_TABLES")
    def _custom_tables(self, **_) -> Dict[str, Any]:
        tables = []
        for name in ["ZCUST_HEADER", "ZCUST_ITEM", "ZMAT_EXTENSION", "ZVEND_MASTER",
                     "ZPRICE_COND", "ZFIN_ALLOC", "ZHR_CUSTOM", "ZMM_RESERVE",
                     "ZSD_DELIVERY", "ZPLANT_CONFIG"]:
            tables.append({
                "TABNAME": name,
                "DEVCLASS": random.choice(_PACKAGES),
                "CNAM": random.choice(_OWNERS),
                "UDAT": _rnd_date(),
            })
        return {"TABLES": tables}

    @_register("Z_GET_ENHANCEMENTS")
    def _enhancements(self, **_) -> Dict[str, Any]:
        return {
            "ENHANCEMENTS": [
                {"ENHNAME": "ZMM_PO_ENHANCEMENT", "TYPE": "BADI", "DEVCLASS": "ZMM"},
                {"ENHNAME": "ZSD_ORDER_EXIT", "TYPE": "USER_EXIT", "DEVCLASS": "ZSD"},
                {"ENHNAME": "ZFI_POSTING_BADI", "TYPE": "BADI", "DEVCLASS": "ZFIN"},
                {"ENHNAME": "ZHR_PAYROLL_EXIT", "TYPE": "USER_EXIT", "DEVCLASS": "ZHR"},
                {"ENHNAME": "ZPP_PROD_ORDER_BADI", "TYPE": "BADI", "DEVCLASS": "ZCUSTOM"},
            ]
        }

    # ── ATC ──────────────────────────────────────────────────────────────────

    @_register("SCI_RUN_CHECK")
    def _run_atc(self, **_) -> Dict[str, Any]:
        return {"RUN_ID": "ATC_RUN_20240101_001", "STATUS": "COMPLETED"}

    @_register("SCI_GET_RESULTS")
    def _atc_results(self, **_) -> Dict[str, Any]:
        findings = []
        obsolete_fms = [
            ("WRITE_FORM", "Obsolete: use OPEN_FORM/CLOSE_FORM or Smart Forms"),
            ("BDC_INSERT", "Performance: use direct call instead"),
            ("CALL_FUNCTION_USING_METHOD", "Obsolete API in S/4HANA"),
            ("CONVERSION_EXIT_ALPHA_INPUT", "Use CL_ABAP_CONV_CODEPAGE instead"),
            ("LIST_FROM_MEMORY", "Removed in S/4HANA – use CL_SALV_TABLE"),
        ]
        for i, (fm, msg) in enumerate(obsolete_fms * 3):
            findings.append({
                "OBJECT": f"ZCUST_REPORT_{(i % 50) + 1:03d}",
                "OBJECT_TYPE": "PROG",
                "CHECK_ID": f"CL_CI_TEST_OBSOLETE_STATEMENTS/CHECK_{i:02d}",
                "CHECK_TITLE": "Obsolete Statement Usage",
                "MESSAGE": msg,
                "PRIORITY": random.choice(["1", "2", "2", "3", "3", "3"]),
                "LINE": random.randint(10, 500),
                "CATEGORY": random.choice(["OBSOLETE_API", "PERFORMANCE", "SECURITY"]),
            })
        # Add a few critical security findings
        for j in range(5):
            findings.append({
                "OBJECT": f"ZCL_MIGRATION_UTIL_{(j % 20) + 1:02d}",
                "OBJECT_TYPE": "CLAS",
                "CHECK_ID": f"CL_CI_TEST_SQL_INJECTION/CHECK_{j:02d}",
                "CHECK_TITLE": "SQL Injection Risk",
                "MESSAGE": "Dynamic SQL without proper escaping detected",
                "PRIORITY": "1",
                "LINE": random.randint(50, 300),
                "CATEGORY": "SECURITY",
            })
        return {"FINDINGS": findings}

    # ── Transport landscape ───────────────────────────────────────────────────

    @_register("TMS_MGR_GET_LANDSCAPE_INFO")
    def _transport_landscape(self, **_) -> Dict[str, Any]:
        return {
            "SYSTEMS": [
                {"SYSNAM": "ECD", "CATEGORY": "D", "DESC": "ECC Development"},
                {"SYSNAM": "ECQ", "CATEGORY": "Q", "DESC": "ECC Quality"},
                {"SYSNAM": "ECC", "CATEGORY": "P", "DESC": "ECC Production"},
            ],
            "ROUTES": [
                {"FROM": "ECD", "TO": "ECQ"},
                {"FROM": "ECQ", "TO": "ECC"},
            ],
        }

    def close(self) -> None:
        log.debug("MockRFCClient closed")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
