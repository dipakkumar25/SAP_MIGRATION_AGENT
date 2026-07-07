"""
Agent 4 – Simplification Database Assessment
Checks custom objects against the SAP S/4HANA Simplification Database.
"""
from __future__ import annotations

from datetime import datetime

from app.models.schemas import (
    AgentState, RiskLevel, SimplificationItem, SimplificationReport,
)
from app.services import get_logger

log = get_logger(__name__)

# ── Embedded simplification DB (comprehensive subset of real SAP items) ───────
_SIMPLIFICATION_DB = {
    "REMOVED_TRANSACTIONS": [
        {"item_id": "SI-001", "object": "SM04",    "title": "SM04 removed – use RZ12",                   "note": "Use transaction RZ12 in S/4HANA",                        "impact": "medium"},
        {"item_id": "SI-002", "object": "SE16",    "title": "SE16 limited in S/4HANA",                   "note": "Use SE16N instead",                                      "impact": "low"},
        {"item_id": "SI-003", "object": "FBL1N",   "title": "FBL1N replaced by Fiori app",               "note": "Use Fiori app F0048",                                    "impact": "medium"},
        {"item_id": "SI-004", "object": "MR21",    "title": "MR21 price change restricted",              "note": "Use MR21 Fiori app in S/4HANA",                          "impact": "medium"},
        {"item_id": "SI-005", "object": "FS10N",   "title": "FS10N replaced in Universal Journal",       "note": "Use FAGLB03 equivalent Fiori tile",                      "impact": "medium"},
        {"item_id": "SI-006", "object": "F.01",    "title": "F.01 balance sheet removed",                "note": "Use Financial Statements Fiori app",                     "impact": "high"},
        {"item_id": "SI-007", "object": "MB52",    "title": "MB52 warehouse stocks – use S/4 app",       "note": "Use Manage Inventory Fiori app",                         "impact": "low"},
        {"item_id": "SI-008", "object": "ME2M",    "title": "ME2M purchase order reporting changed",     "note": "Use Manage Purchase Orders Fiori app",                   "impact": "medium"},
    ],
    "DEPRECATED_FMS": [
        {"item_id": "SI-010", "object": "WRITE_FORM",                  "title": "WRITE_FORM deprecated",                  "note": "Replace with Smart Forms or Adobe Forms",               "impact": "high"},
        {"item_id": "SI-011", "object": "LIST_FROM_MEMORY",            "title": "LIST_FROM_MEMORY removed",               "note": "Use CL_SALV_TABLE",                                     "impact": "critical"},
        {"item_id": "SI-012", "object": "CONVERSION_EXIT_ALPHA_INPUT", "title": "Alpha conversion exit API changed",      "note": "Use ALPHA_CONVERSION_EXIT",                             "impact": "medium"},
        {"item_id": "SI-013", "object": "REUSE_ALV_GRID_DISPLAY",      "title": "REUSE_ALV deprecated",                   "note": "Migrate to CL_SALV_TABLE / Fiori",                      "impact": "high"},
        {"item_id": "SI-014", "object": "BDC_INSERT",                  "title": "BDC_INSERT performance issue",           "note": "Use direct BAPI calls",                                 "impact": "medium"},
        {"item_id": "SI-015", "object": "REUSE_ALV_LIST_DISPLAY",      "title": "REUSE_ALV_LIST_DISPLAY deprecated",      "note": "Migrate to CL_SALV_TABLE",                              "impact": "high"},
        {"item_id": "SI-016", "object": "HR_INFOTYPE_OPERATION",       "title": "HR infotype FM deprecated",              "note": "Use HCMFAB Personnel Administration API",               "impact": "high"},
        {"item_id": "SI-017", "object": "RFC_READ_TABLE",              "title": "RFC_READ_TABLE performance issue",       "note": "Use CDS views or OData services instead",               "impact": "medium"},
        {"item_id": "SI-018", "object": "BAPI_MATERIAL_SAVEDATA",      "title": "Material BAPI interface changed",        "note": "Use S/4HANA API_PRODUCT_SRV OData service",             "impact": "high"},
        {"item_id": "SI-019", "object": "SD_SALESDOCUMENT_CREATE",     "title": "SD document creation FM changed",       "note": "Use BAPI_SALESORDER_CREATEFROMDAT2",                    "impact": "high"},
    ],
    "DEPRECATED_TABLES": [
        {"item_id": "SI-020", "object": "BSEG",      "title": "BSEG split in Universal Journal",           "note": "Use ACDOCA for all FI postings",                         "impact": "critical"},
        {"item_id": "SI-021", "object": "FAGLFLEXT", "title": "FAGLFLEXT replaced by ACDOCA",              "note": "Universal Journal migration required",                   "impact": "critical"},
        {"item_id": "SI-022", "object": "KNC1",      "title": "Customer account totals changed",           "note": "Use BPKONA view in S/4HANA",                             "impact": "high"},
        {"item_id": "SI-023", "object": "LFC1",      "title": "Vendor account totals changed",             "note": "Use BPKONA view in S/4HANA",                             "impact": "high"},
        {"item_id": "SI-024", "object": "BKPF",      "title": "BKPF read via ACDOCA",                     "note": "Use ACDOCA for journal entry access",                    "impact": "high"},
        {"item_id": "SI-025", "object": "COEP",      "title": "COEP CO line items via ACDOCA",             "note": "Read controlling line items from ACDOCA",               "impact": "high"},
        {"item_id": "SI-026", "object": "COSS",      "title": "COSS cost object totals changed",           "note": "Use ACDOCA for cost object reporting",                  "impact": "high"},
        {"item_id": "SI-027", "object": "MARC",      "title": "MARC plant data – new S/4 structure",       "note": "Additional plant data fields in S/4HANA material master","impact": "medium"},
        {"item_id": "SI-028", "object": "MARA",      "title": "MARA material master restructured",         "note": "New fields for product classification in S/4HANA",      "impact": "medium"},
        {"item_id": "SI-029", "object": "VBAK",      "title": "VBAK sales order header – Fiori read",      "note": "Use CDS views over direct VBAK access",                 "impact": "medium"},
    ],
    "COMPATIBILITY_VIEWS": [
        {"item_id": "SI-030", "object": "MARA_VIEW",  "title": "MARA compatibility view",                  "note": "Migrate to S/4HANA material master API",                "impact": "medium"},
        {"item_id": "SI-031", "object": "KNVV_VIEW",  "title": "Customer sales data view",                 "note": "Use Business Partner concept for customer data",        "impact": "high"},
        {"item_id": "SI-032", "object": "KNA1_VIEW",  "title": "KNA1 general customer view",               "note": "Customer data moved to Business Partner",               "impact": "high"},
        {"item_id": "SI-033", "object": "LFA1_VIEW",  "title": "LFA1 vendor general view",                 "note": "Vendor data moved to Business Partner",                 "impact": "high"},
        {"item_id": "SI-034", "object": "EKPO_VIEW",  "title": "EKPO purchase order items compat view",    "note": "Use CDS view C_PurchaseOrderItemTP",                    "impact": "medium"},
    ],
    "UNIVERSAL_JOURNAL": [
        {"item_id": "SI-040", "object": "CO-PA",       "title": "CO-PA integrated into Universal Journal",  "note": "ACDOCA replaces CE4XXXX profitability tables",          "impact": "critical"},
        {"item_id": "SI-041", "object": "COSS/COSP",   "title": "Cost object totals tables changed",        "note": "Use ACDOCA for cost object reporting",                  "impact": "high"},
        {"item_id": "SI-042", "object": "FAGLFLEXA",   "title": "New GL line items in ACDOCA",              "note": "Migrate custom FI line item reports to ACDOCA",         "impact": "critical"},
        {"item_id": "SI-043", "object": "FAGLFLEXT",   "title": "New GL totals in ACDOCA",                  "note": "All G/L totals now sourced from ACDOCA",                "impact": "critical"},
        {"item_id": "SI-044", "object": "CE4XXXX",     "title": "CO-PA tables CE4XXXX removed",             "note": "Account-based CO-PA mandatory, table-based removed",    "impact": "critical"},
    ],
    "BUSINESS_PARTNER": [
        {"item_id": "SI-050", "object": "KUNNR",  "title": "Customer must be Business Partner",       "note": "Execute BP migration (transaction FLBP) before go-live",    "impact": "critical"},
        {"item_id": "SI-051", "object": "LIFNR",  "title": "Vendor must be Business Partner",         "note": "Execute BP migration (transaction FLBP) before go-live",    "impact": "critical"},
        {"item_id": "SI-052", "object": "KNA1",   "title": "KNA1 customer master – BP mandatory",     "note": "All KNA1 records need BP counterpart",                      "impact": "critical"},
        {"item_id": "SI-053", "object": "LFA1",   "title": "LFA1 vendor master – BP mandatory",       "note": "All LFA1 records need BP counterpart",                      "impact": "critical"},
        {"item_id": "SI-054", "object": "KNVV",   "title": "Customer sales area data linked to BP",   "note": "Sales area data must be maintained on BP",                  "impact": "high"},
        {"item_id": "SI-055", "object": "LFAS",   "title": "Vendor withholding tax linked to BP",     "note": "Withholding tax configuration on BP",                       "impact": "medium"},
    ],
    "MATERIAL_LEDGER": [
        {"item_id": "SI-060", "object": "Material Ledger",  "title": "Material Ledger mandatory",       "note": "Activate material ledger for all plants before migration",  "impact": "high"},
        {"item_id": "SI-061", "object": "CKMLCR",           "title": "CKMLCR table impact",             "note": "Price control changes and ML activation required",          "impact": "medium"},
        {"item_id": "SI-062", "object": "CKMVFM",           "title": "Material value flow changed",     "note": "Use ML reports for stock valuation in S/4HANA",            "impact": "medium"},
        {"item_id": "SI-063", "object": "MBEW",             "title": "MBEW valuation data in S/4HANA",  "note": "Material valuation restructured with mandatory ML",         "impact": "high"},
    ],
}

_IMPACT_MAP = {
    "critical": RiskLevel.CRITICAL,
    "high": RiskLevel.HIGH,
    "medium": RiskLevel.MEDIUM,
    "low": RiskLevel.LOW,
}


def _check_affected(item_obj: str, state: AgentState) -> bool:
    """Heuristic: check if the object appears in custom code or standard usage."""
    if not state.custom_code:
        return True  # Assume affected if we have no data
    all_names = (
        [o.object_name for o in state.custom_code.z_programs] +
        [o.object_name for o in state.custom_code.z_function_modules] +
        [o.object_name for o in state.custom_code.custom_tables]
    )
    # Also check ATC findings
    if state.atc_report:
        atc_msgs = " ".join(f.message for f in state.atc_report.findings)
        if item_obj.upper() in atc_msgs.upper():
            return True
    return any(item_obj.upper() in name.upper() for name in all_names)


def run_simplification_analysis(state: AgentState) -> AgentState:
    """LangGraph node: cross-reference landscape against simplification DB."""
    log.info("Agent 4 – Simplification Analysis started", assessment_id=state.assessment_id)
    try:
        def _build_items(raw_list: list, category: str) -> list[SimplificationItem]:
            items = []
            for raw in raw_list:
                items.append(SimplificationItem(
                    item_id=raw["item_id"],
                    title=raw["title"],
                    category=category,
                    object_name=raw["object"],
                    description=raw["title"],
                    impact=_IMPACT_MAP.get(raw["impact"], RiskLevel.LOW),
                    affected_in_system=_check_affected(raw["object"], state),
                    migration_note=raw.get("note"),
                ))
            return items

        removed_tx      = _build_items(_SIMPLIFICATION_DB["REMOVED_TRANSACTIONS"], "REMOVED_TRANSACTION")
        deprecated_fms  = _build_items(_SIMPLIFICATION_DB["DEPRECATED_FMS"], "DEPRECATED_FM")
        deprecated_tabs = _build_items(_SIMPLIFICATION_DB["DEPRECATED_TABLES"], "DEPRECATED_TABLE")
        compat_views    = _build_items(_SIMPLIFICATION_DB["COMPATIBILITY_VIEWS"], "COMPATIBILITY_VIEW")
        uj_impacts      = _build_items(_SIMPLIFICATION_DB["UNIVERSAL_JOURNAL"], "UNIVERSAL_JOURNAL")
        bp_items        = _build_items(_SIMPLIFICATION_DB["BUSINESS_PARTNER"], "BUSINESS_PARTNER")
        ml_items        = _build_items(_SIMPLIFICATION_DB["MATERIAL_LEDGER"], "MATERIAL_LEDGER")

        all_items = removed_tx + deprecated_fms + deprecated_tabs + compat_views + uj_impacts + bp_items + ml_items
        critical_count = sum(1 for i in all_items if i.impact == RiskLevel.CRITICAL and i.affected_in_system)

        state.simplification_report = SimplificationReport(
            removed_transactions=removed_tx,
            deprecated_function_modules=deprecated_fms,
            deprecated_tables=deprecated_tabs,
            compatibility_views=compat_views,
            universal_journal_impacts=uj_impacts,
            business_partner_items=bp_items,
            material_ledger_items=ml_items,
            total_impacts=len(all_items),
            critical_impacts=critical_count,
            analyzed_at=datetime.utcnow(),
        )

        state.steps_completed.append("simplification_analysis")
        state.current_step = "dependency_analysis"
        log.info("Agent 4 – completed",
                 total_impacts=len(all_items),
                 critical=critical_count)

    except Exception as exc:
        log.error("Agent 4 – failed", error=str(exc))
        state.error_messages.append(f"Simplification Analysis: {exc}")

    return state
