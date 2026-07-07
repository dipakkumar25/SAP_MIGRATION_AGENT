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

# ── Embedded simplification DB (subset of real SAP simplification items) ──────
_SIMPLIFICATION_DB = {
    "REMOVED_TRANSACTIONS": [
        {"item_id": "SI-001", "object": "SM04", "title": "SM04 removed – use RZ12", "note": "Use transaction RZ12 in S/4HANA", "impact": "medium"},
        {"item_id": "SI-002", "object": "SE16", "title": "SE16 limited in S/4HANA", "note": "Use SE16N instead", "impact": "low"},
        {"item_id": "SI-003", "object": "FBL1N", "title": "FBL1N replaced by Fiori app", "note": "Use Fiori app F0048", "impact": "medium"},
    ],
    "DEPRECATED_FMS": [
        {"item_id": "SI-010", "object": "WRITE_FORM", "title": "WRITE_FORM deprecated", "note": "Replace with Smart Forms or Adobe Forms", "impact": "high"},
        {"item_id": "SI-011", "object": "LIST_FROM_MEMORY", "title": "LIST_FROM_MEMORY removed", "note": "Use CL_SALV_TABLE", "impact": "critical"},
        {"item_id": "SI-012", "object": "CONVERSION_EXIT_ALPHA_INPUT", "title": "Alpha conversion exit API changed", "note": "Use ALPHA_CONVERSION_EXIT", "impact": "medium"},
        {"item_id": "SI-013", "object": "REUSE_ALV_GRID_DISPLAY", "title": "REUSE_ALV deprecated", "note": "Migrate to CL_SALV_TABLE / Fiori", "impact": "high"},
        {"item_id": "SI-014", "object": "BDC_INSERT", "title": "BDC_INSERT performance issue", "note": "Use direct BAPI calls", "impact": "medium"},
    ],
    "DEPRECATED_TABLES": [
        {"item_id": "SI-020", "object": "BSEG", "title": "BSEG table split in Universal Journal", "note": "Use ACDOCA for FI postings", "impact": "critical"},
        {"item_id": "SI-021", "object": "FAGLFLEXT", "title": "FAGLFLEXT replaced by ACDOCA", "note": "Universal Journal migration required", "impact": "critical"},
        {"item_id": "SI-022", "object": "KNC1", "title": "Customer account totals changed", "note": "Use BPKONA view", "impact": "high"},
        {"item_id": "SI-023", "object": "LFC1", "title": "Vendor account totals changed", "note": "Use BPKONA view", "impact": "high"},
        {"item_id": "SI-024", "object": "BKPF", "title": "BKPF read via ACDOCA", "note": "Use ACDOCA for journal entries", "impact": "high"},
    ],
    "COMPATIBILITY_VIEWS": [
        {"item_id": "SI-030", "object": "MARA_VIEW", "title": "MARA compatibility view", "note": "Migrate to S4 material master", "impact": "medium"},
        {"item_id": "SI-031", "object": "KNVV_VIEW", "title": "Customer sales data view", "note": "Use Business Partner concept", "impact": "high"},
    ],
    "UNIVERSAL_JOURNAL": [
        {"item_id": "SI-040", "object": "CO-PA", "title": "CO-PA integrated into Universal Journal", "note": "ACDOCA replaces CE4XXXX tables", "impact": "critical"},
        {"item_id": "SI-041", "object": "COSS/COSP", "title": "Cost object totals tables changed", "note": "Use ACDOCA", "impact": "high"},
    ],
    "BUSINESS_PARTNER": [
        {"item_id": "SI-050", "object": "KUNNR", "title": "Customer must be Business Partner", "note": "Run BP migration before go-live", "impact": "critical"},
        {"item_id": "SI-051", "object": "LIFNR", "title": "Vendor must be Business Partner", "note": "Run BP migration before go-live", "impact": "critical"},
    ],
    "MATERIAL_LEDGER": [
        {"item_id": "SI-060", "object": "Material Ledger", "title": "Material Ledger mandatory in S/4HANA", "note": "Activate material ledger for all plants", "impact": "high"},
        {"item_id": "SI-061", "object": "CKMLCR", "title": "CKMLCR table impact in S/4HANA", "note": "Price control changes required", "impact": "medium"},
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
