"""
Mock SAP RFC client.

Simulates RFC function module responses so the agent pipeline can run
end-to-end without a live SAP system.  All data matches a realistic
ECC 6.0 EHP8 landscape with a large custom-code footprint across FI, MM,
SD, HR, PP, WM, PM, QM and cross-module integration objects.
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

_OWNERS = [
    "JOHN_S", "MARIA_K", "DEV_TEAM", "BASIS_ADM", "ABAP_DEV",
    "HANS_M",  "PRIYA_R", "LEI_Z",   "CARLOS_V", "ANNA_B",
    "FRANK_W", "SARA_T",  "MIKE_O",  "INES_P",   "RAVI_N",
]
_PACKAGES = [
    "ZCUSTOM", "ZFIN", "ZMM", "ZSD", "ZHR",
    "ZUTILS",  "ZMIG", "ZPP", "ZWM", "ZPM",
    "ZQM",     "ZCO",  "ZPS", "ZIS", "ZINT",
]
_TRANSPORT_PREFIX = "ECCK9"

# SAP modules mapped to meaningful name prefixes
_MODULE_PROGRAMS = {
    "FI":  ("ZFIN_", "ZFI_", "ZAP_", "ZGL_", "ZAR_"),
    "MM":  ("ZMM_",  "ZPO_", "ZGR_", "ZMAT_","ZINV_"),
    "SD":  ("ZSD_",  "ZOR_", "ZDL_", "ZBI_", "ZPRC_"),
    "HR":  ("ZHR_",  "ZPA_", "ZPY_", "ZTM_", "ZORG_"),
    "PP":  ("ZPP_",  "ZMO_", "ZCA_", "ZWIP_","ZPLN_"),
    "WM":  ("ZWM_",  "ZWT_", "ZST_", "ZBWM_","ZTRN_"),
    "PM":  ("ZPM_",  "ZWO_", "ZNO_", "ZPLM_","ZEQP_"),
    "QM":  ("ZQM_",  "ZQN_", "ZQI_", "ZINSP","ZRES_"),
    "CO":  ("ZCO_",  "ZCE_", "ZCPA_","ZCOS_","ZIO_"),
    "INT": ("ZINT_", "ZBAPI_","ZRFC_","ZIDOC_","ZAPI_"),
}

_OBSOLETE_FMS = [
    ("WRITE_FORM",                  "Obsolete: use OPEN_FORM/CLOSE_FORM or Smart Forms"),
    ("BDC_INSERT",                  "Performance: use direct BAPI call instead"),
    ("CALL_FUNCTION_USING_METHOD",  "Obsolete API removed in S/4HANA"),
    ("CONVERSION_EXIT_ALPHA_INPUT", "Use CL_ABAP_CONV_CODEPAGE instead"),
    ("LIST_FROM_MEMORY",            "Removed in S/4HANA – use CL_SALV_TABLE"),
    ("REUSE_ALV_GRID_DISPLAY",      "Deprecated – migrate to CL_SALV_TABLE or Fiori"),
    ("REUSE_ALV_LIST_DISPLAY",      "Deprecated – migrate to CL_SALV_TABLE"),
    ("RS_COVERPAGE_SELECTIONS",     "Removed in S/4HANA – use ALV"),
    ("POPUP_TO_SELECT_MONTH",       "Deprecated – use custom date selection"),
    ("ENQUEUE_E_TABLE",             "Use object-based locking instead"),
    ("HR_INFOTYPE_OPERATION",       "Deprecated – use HCMFAB API"),
    ("RFC_READ_TABLE",              "Performance issue – use CDS views"),
    ("BAPI_MATERIAL_SAVEDATA",      "Use S/4HANA API_PRODUCT_* instead"),
    ("BAPI_PO_CREATE1",             "Review: enhanced MM_PO_* API recommended"),
    ("SD_SALESDOCUMENT_CREATE",     "Use BAPI_SALESORDER_CREATEFROMDAT2"),
]

_SECURITY_ISSUES = [
    ("Dynamic SQL without input validation",          "SECURITY"),
    ("Hardcoded password in program",                 "SECURITY"),
    ("Missing authority check before DB operation",   "SECURITY"),
    ("Direct SELECT * without WHERE clause",          "PERFORMANCE"),
    ("Unescaped user input in dynamic WHERE clause",  "SECURITY"),
    ("RFC destination with stored credentials",       "SECURITY"),
    ("Missing SY-SUBRC check after RFC call",         "ROBUSTNESS"),
    ("CATCH without CLEANUP block",                   "ROBUSTNESS"),
    ("Obsolete SELECT SINGLE with no unique key",     "PERFORMANCE"),
    ("Use of FIELD-SYMBOLS without type-safety",      "PERFORMANCE"),
]


def _rnd_date(days_back: int = 730) -> str:
    d = datetime.utcnow() - timedelta(days=random.randint(0, days_back))
    return d.strftime("%Y%m%d")

def _transport() -> str:
    return f"{_TRANSPORT_PREFIX}{random.randint(100000, 999999)}"

def _pick_module() -> str:
    return random.choice(list(_MODULE_PROGRAMS.keys()))

def _prog_name(module: str, idx: int) -> str:
    prefix = random.choice(_MODULE_PROGRAMS[module])
    return f"{prefix}REPORT_{idx:04d}"

def _fm_name(module: str, idx: int) -> str:
    verbs = ["CALC", "GET", "SET", "POST", "CHECK", "READ", "WRITE",
             "PROCESS", "VALIDATE", "CONVERT", "CREATE", "UPDATE", "DELETE"]
    nouns = ["INVOICE", "ORDER", "MATERIAL", "VENDOR", "CUSTOMER", "COST",
             "PAYMENT", "DELIVERY", "TRANSFER", "POSITION", "BATCH", "PLANT"]
    return f"Z_{random.choice(verbs)}_{random.choice(nouns)}_{idx:04d}"

def _class_name(module: str, idx: int) -> str:
    patterns = ["ZCL_{mod}_HANDLER_{i:03d}", "ZCL_{mod}_PROCESSOR_{i:03d}",
                "ZCL_{mod}_VALIDATOR_{i:03d}", "ZCL_{mod}_FACTORY_{i:03d}",
                "ZCL_{mod}_UTIL_{i:03d}", "ZIF_{mod}_SERVICE_{i:03d}"]
    tpl = random.choice(patterns)
    return tpl.format(mod=module, i=idx)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level dispatch (avoids NameError on Python 3.12+ class-body scoping)
# ─────────────────────────────────────────────────────────────────────────────

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
        log.info("MockRFCClient initialised",
                 params={k: v for k, v in params.items() if k != "passwd"})

    def call(self, func_module: str, **kwargs: Any) -> Dict[str, Any]:
        log.debug("RFC call", func_module=func_module)
        method = self._dispatch.get(func_module)
        if method is None:
            raise NotImplementedError(f"Mock not implemented for: {func_module}")
        return method(self, **kwargs)

    # ── System info ──────────────────────────────────────────────────────────

    @_register("RFC_SYSTEM_INFO")
    def _system_info(self, **_) -> Dict[str, Any]:
        return {
            "RFCSI_EXPORT": {
                "RFCSYSID": "ECC",
                "RFCHOST":  "sapeccprd.company.com",
                "RFCDBHOST":"sapdbprd.company.com",
                "RFCDBSYS": "HDB",
                "RFCSAPRL": "740",
                "RFCKERNRL":"753",
            }
        }

    @_register("TH_SERVER_LIST")
    def _server_list(self, **_) -> Dict[str, Any]:
        return {
            "LIST": [
                {"NAME": "sapeccprd_ECC_00", "HOST": "sapeccprd.company.com",  "USERS": 312},
                {"NAME": "sapeccprd_ECC_01", "HOST": "sapeccprd2.company.com", "USERS": 198},
            ]
        }

    @_register("SUSR_GET_ADMIN_USER_LOGIN_INFO")
    def _client_list(self, **_) -> Dict[str, Any]:
        return {
            "CLIENTS": [
                {"MANDT": "100", "MTEXT": "Production",  "ORT01": "Frankfurt"},
                {"MANDT": "200", "MTEXT": "Quality",     "ORT01": "Frankfurt"},
                {"MANDT": "300", "MTEXT": "Development", "ORT01": "Frankfurt"},
                {"MANDT": "400", "MTEXT": "Training",    "ORT01": "Berlin"},
                {"MANDT": "500", "MTEXT": "Sandbox",     "ORT01": "Berlin"},
            ]
        }

    @_register("RFC_GET_LOCAL_DESTINATIONS")
    def _rfc_destinations(self, **_) -> Dict[str, Any]:
        dests = []
        for d in ["ECC_QUALITY", "BW_PRD", "CRM_PRD", "PI_PRD", "MDG_PRD",
                  "GTS_PRD",     "APO_PRD","SRM_PRD", "HCM_PRD","CCP_PRD"]:
            dests.append({
                "RFCDEST": d,
                "RFCTYPE": "3",
                "RFCHOST": f"{d.lower()}.company.com",
            })
        return {"DESTINATIONS": dests}

    @_register("DELIVERY_GET_PACKAGES")
    def _addon_list(self, **_) -> Dict[str, Any]:
        return {
            "PACKS": [
                {"COMPONENT": "SAP_BASIS",  "RELEASE": "740", "SP_LEVEL": "SP25"},
                {"COMPONENT": "SAP_APPL",   "RELEASE": "617", "SP_LEVEL": "SP08"},
                {"COMPONENT": "SAP_HR",     "RELEASE": "617", "SP_LEVEL": "SP08"},
                {"COMPONENT": "FINBASIS",   "RELEASE": "617", "SP_LEVEL": "SP08"},
                {"COMPONENT": "IS_OIL",     "RELEASE": "617", "SP_LEVEL": "SP03"},
                {"COMPONENT": "EA_APPL",    "RELEASE": "617", "SP_LEVEL": "SP08"},
                {"COMPONENT": "EA_FIN",     "RELEASE": "617", "SP_LEVEL": "SP08"},
                {"COMPONENT": "EA_HR",      "RELEASE": "617", "SP_LEVEL": "SP08"},
                {"COMPONENT": "BBPCRM",     "RELEASE": "740", "SP_LEVEL": "SP10"},
                {"COMPONENT": "SEM_BW",     "RELEASE": "617", "SP_LEVEL": "SP06"},
            ]
        }

    @_register("DB6_GET_DB_SYSTEM_INFO")
    def _hana_info(self, **_) -> Dict[str, Any]:
        return {
            "DB_SYSTEM":  "SAP HANA",
            "DB_RELEASE": "2.0 SP07",
            "DB_HOST":    "sapdbprd.company.com",
        }

    # ── Custom code ──────────────────────────────────────────────────────────

    @_register("Z_GET_CUSTOM_PROGRAMS")
    def _custom_programs(self, **_) -> Dict[str, Any]:
        random.seed(42)
        progs = []
        idx = 1
        # 25 programs per module across 10 modules = 250 programs
        for module, _ in _MODULE_PROGRAMS.items():
            for _ in range(25):
                progs.append({
                    "PROGNAME": _prog_name(module, idx),
                    "DEVCLASS": random.choice(_PACKAGES),
                    "CNAM":     random.choice(_OWNERS),
                    "UNAM":     random.choice(_OWNERS),
                    "UDAT":     _rnd_date(),
                    "LINES":    random.randint(50, 4500),
                    "TRKORR":   _transport(),
                })
                idx += 1
        return {"PROGRAMS": progs}

    @_register("Z_GET_FUNCTION_MODULES")
    def _function_modules(self, **_) -> Dict[str, Any]:
        random.seed(43)
        fms = []
        idx = 1
        # 8 FMs per module = 80 total
        for module in _MODULE_PROGRAMS:
            for _ in range(8):
                fms.append({
                    "FUNCNAME": _fm_name(module, idx),
                    "DEVCLASS": random.choice(_PACKAGES),
                    "CNAM":     random.choice(_OWNERS),
                    "UDAT":     _rnd_date(),
                    "LINES":    random.randint(30, 1200),
                    "TRKORR":   _transport(),
                })
                idx += 1
        return {"FUNCTION_MODULES": fms}

    @_register("Z_GET_CLASSES")
    def _classes(self, **_) -> Dict[str, Any]:
        random.seed(44)
        clazzes = []
        idx = 1
        # 5 classes per module = 50 total
        for module in _MODULE_PROGRAMS:
            for _ in range(5):
                clazzes.append({
                    "CLSNAME":  _class_name(module, idx),
                    "DEVCLASS": random.choice(_PACKAGES),
                    "CNAM":     random.choice(_OWNERS),
                    "UDAT":     _rnd_date(),
                    "LINES":    random.randint(100, 3000),
                    "TRKORR":   _transport(),
                })
                idx += 1
        return {"CLASSES": clazzes}

    @_register("Z_GET_CUSTOM_TABLES")
    def _custom_tables(self, **_) -> Dict[str, Any]:
        tables = [
            # FI
            "ZCUST_HEADER",  "ZCUST_ITEM",   "ZFIN_ALLOC",   "ZGL_ACCRUAL",
            "ZAP_PAYMENT",
            # MM
            "ZMAT_EXTENSION","ZVEND_MASTER",  "ZPRICE_COND",  "ZMM_RESERVE",
            "ZPURCH_HIST",
            # SD
            "ZSD_DELIVERY",  "ZCUST_ORDER",   "ZPRICE_LIST",  "ZSD_ROUTE",
            "ZBILLING_DOC",
            # HR
            "ZHR_CUSTOM",    "ZEMPLOYEE_EXT", "ZPAYROLL_OT",  "ZPA_ACTIONS",
            "ZORG_ASSIGN",
            # PP/WM/PM
            "ZPLANT_CONFIG", "ZPP_WORKCTR",   "ZWM_TRANSFER", "ZPM_NOTIF",
            "ZQM_RESULT",
        ]
        result = []
        for name in tables:
            result.append({
                "TABNAME":  name,
                "DEVCLASS": random.choice(_PACKAGES),
                "CNAM":     random.choice(_OWNERS),
                "UDAT":     _rnd_date(),
            })
        return {"TABLES": result}

    @_register("Z_GET_ENHANCEMENTS")
    def _enhancements(self, **_) -> Dict[str, Any]:
        return {
            "ENHANCEMENTS": [
                # BADIs
                {"ENHNAME": "ZMM_PO_BADI",          "TYPE": "BADI",      "DEVCLASS": "ZMM"},
                {"ENHNAME": "ZSD_ORDER_BADI",        "TYPE": "BADI",      "DEVCLASS": "ZSD"},
                {"ENHNAME": "ZFI_POSTING_BADI",      "TYPE": "BADI",      "DEVCLASS": "ZFIN"},
                {"ENHNAME": "ZHR_PAYROLL_BADI",      "TYPE": "BADI",      "DEVCLASS": "ZHR"},
                {"ENHNAME": "ZPP_PROD_ORDER_BADI",   "TYPE": "BADI",      "DEVCLASS": "ZCUSTOM"},
                {"ENHNAME": "ZQM_INSPECTION_BADI",   "TYPE": "BADI",      "DEVCLASS": "ZQM"},
                {"ENHNAME": "ZPM_NOTIF_BADI",        "TYPE": "BADI",      "DEVCLASS": "ZPM"},
                {"ENHNAME": "ZCO_SETTLEMENT_BADI",   "TYPE": "BADI",      "DEVCLASS": "ZCO"},
                # User Exits
                {"ENHNAME": "ZSD_ORDER_EXIT",        "TYPE": "USER_EXIT", "DEVCLASS": "ZSD"},
                {"ENHNAME": "ZHR_PAYROLL_EXIT",      "TYPE": "USER_EXIT", "DEVCLASS": "ZHR"},
                {"ENHNAME": "ZMM_GR_EXIT",           "TYPE": "USER_EXIT", "DEVCLASS": "ZMM"},
                {"ENHNAME": "ZFI_DOCUMENT_EXIT",     "TYPE": "USER_EXIT", "DEVCLASS": "ZFIN"},
                {"ENHNAME": "ZPP_CONFIRM_EXIT",      "TYPE": "USER_EXIT", "DEVCLASS": "ZPP"},
                {"ENHNAME": "ZWM_TRANSFER_EXIT",     "TYPE": "USER_EXIT", "DEVCLASS": "ZWM"},
                # Enhancement Spots
                {"ENHNAME": "ZSD_PRICING_ESPOT",     "TYPE": "ESPOT",     "DEVCLASS": "ZSD"},
                {"ENHNAME": "ZFI_CLEARING_ESPOT",    "TYPE": "ESPOT",     "DEVCLASS": "ZFIN"},
            ]
        }

    # ── ATC ──────────────────────────────────────────────────────────────────

    @_register("SCI_RUN_CHECK")
    def _run_atc(self, **_) -> Dict[str, Any]:
        return {"RUN_ID": "ATC_RUN_20240601_001", "STATUS": "COMPLETED"}

    @_register("SCI_GET_RESULTS")
    def _atc_results(self, **_) -> Dict[str, Any]:
        random.seed(99)
        findings = []

        # ── Obsolete FM findings spread across programs (40 findings) ────────
        prog_names = [_prog_name(m, i) for m in _MODULE_PROGRAMS for i in range(1, 5)]
        for i, (fm, msg) in enumerate((_OBSOLETE_FMS * 4)[:40]):
            prog = prog_names[i % len(prog_names)]
            findings.append({
                "OBJECT":      prog,
                "OBJECT_TYPE": "PROG",
                "CHECK_ID":    f"CL_CI_TEST_OBSOLETE_STATEMENTS/CHECK_{i:03d}",
                "CHECK_TITLE": "Obsolete Statement / API Usage",
                "MESSAGE":     msg,
                "PRIORITY":    random.choice(["1", "1", "2", "2", "3"]),
                "LINE":        random.randint(10, 800),
                "CATEGORY":    "OBSOLETE_API",
            })

        # ── Security & performance findings on classes (15 findings) ─────────
        class_names = [_class_name(m, i) for m in ["FI", "SD", "MM", "HR", "CO"] for i in range(1, 4)]
        for j, (issue, cat) in enumerate((_SECURITY_ISSUES * 3)[:15]):
            cls = class_names[j % len(class_names)]
            findings.append({
                "OBJECT":      cls,
                "OBJECT_TYPE": "CLAS",
                "CHECK_ID":    f"CL_CI_TEST_SECURITY/CHECK_{j:03d}",
                "CHECK_TITLE": "Security / Performance Violation",
                "MESSAGE":     issue,
                "PRIORITY":    "1" if "SQL" in issue or "password" in issue or "authority" in issue else "2",
                "LINE":        random.randint(20, 500),
                "CATEGORY":    cat,
            })

        # ── Syntax / robustness on function modules (10 findings) ────────────
        fm_names = [_fm_name(m, i) for m in ["MM", "SD", "FI"] for i in range(1, 5)]
        robustness_msgs = [
            "No exception handling around BAPI call",
            "COMMIT WORK inside subroutine – avoid for unit testability",
            "SELECT inside loop – move outside for performance",
            "Implicit type conversion in arithmetic expression",
            "Missing ROLLBACK WORK in error handler",
        ]
        for k, msg in enumerate((robustness_msgs * 2)[:10]):
            fm = fm_names[k % len(fm_names)]
            findings.append({
                "OBJECT":      fm,
                "OBJECT_TYPE": "FUGR",
                "CHECK_ID":    f"CL_CI_TEST_ROBUST/CHECK_{k:03d}",
                "CHECK_TITLE": "Robustness Issue",
                "MESSAGE":     msg,
                "PRIORITY":    random.choice(["2", "3", "3"]),
                "LINE":        random.randint(5, 300),
                "CATEGORY":    "ROBUSTNESS",
            })

        return {"FINDINGS": findings}

    # ── Transport landscape ───────────────────────────────────────────────────

    @_register("TMS_MGR_GET_LANDSCAPE_INFO")
    def _transport_landscape(self, **_) -> Dict[str, Any]:
        return {
            "SYSTEMS": [
                {"SYSNAM": "ECD", "CATEGORY": "D", "DESC": "ECC Development"},
                {"SYSNAM": "ECQ", "CATEGORY": "Q", "DESC": "ECC Quality"},
                {"SYSNAM": "ECU", "CATEGORY": "Q", "DESC": "ECC UAT"},
                {"SYSNAM": "ECC", "CATEGORY": "P", "DESC": "ECC Production"},
            ],
            "ROUTES": [
                {"FROM": "ECD", "TO": "ECQ"},
                {"FROM": "ECQ", "TO": "ECU"},
                {"FROM": "ECU", "TO": "ECC"},
            ],
        }

    def close(self) -> None:
        log.debug("MockRFCClient closed")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
