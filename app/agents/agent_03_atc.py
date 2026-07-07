"""
Agent 3 – ATC Assessment
Runs SAP ATC (ABAP Test Cockpit) checks and classifies findings.
"""
from __future__ import annotations

from datetime import datetime

from app.models.schemas import AgentState, ATCCategory, ATCFinding, ATCReport, RiskLevel
from app.services import get_logger, get_rfc_client

log = get_logger(__name__)

_PRIORITY_MAP = {"1": RiskLevel.CRITICAL, "2": RiskLevel.HIGH, "3": RiskLevel.MEDIUM, "4": RiskLevel.LOW}
_CATEGORY_MAP = {
    "OBSOLETE_API": ATCCategory.OBSOLETE_API,
    "PERFORMANCE": ATCCategory.PERFORMANCE,
    "SECURITY": ATCCategory.SECURITY,
    "SYNTAX": ATCCategory.SYNTAX,
    "STYLE": ATCCategory.STYLE,
    "ROBUSTNESS": ATCCategory.ROBUSTNESS,
}


def run_atc_assessment(state: AgentState) -> AgentState:
    """LangGraph node: execute ATC checks and parse results."""
    log.info("Agent 3 – ATC Assessment started", assessment_id=state.assessment_id)
    try:
        with get_rfc_client() as rfc:
            run_result = rfc.call("SCI_RUN_CHECK")
            run_id = run_result.get("RUN_ID", "")
            raw_findings = rfc.call("SCI_GET_RESULTS", RUN_ID=run_id).get("FINDINGS", [])

        findings: list[ATCFinding] = []
        for raw in raw_findings:
            priority_str = str(raw.get("PRIORITY", "3"))
            cat_str = raw.get("CATEGORY", "SYNTAX").upper()
            findings.append(ATCFinding(
                object_name=raw.get("OBJECT", "UNKNOWN"),
                object_type=raw.get("OBJECT_TYPE", "PROG"),
                check_id=raw.get("CHECK_ID", ""),
                check_title=raw.get("CHECK_TITLE", ""),
                message=raw.get("MESSAGE", ""),
                category=_CATEGORY_MAP.get(cat_str, ATCCategory.SYNTAX),
                priority=_PRIORITY_MAP.get(priority_str, RiskLevel.LOW),
                line_number=int(raw.get("LINE", 0)) or None,
            ))

        critical = sum(1 for f in findings if f.priority == RiskLevel.CRITICAL)
        high     = sum(1 for f in findings if f.priority == RiskLevel.HIGH)
        medium   = sum(1 for f in findings if f.priority == RiskLevel.MEDIUM)
        low      = sum(1 for f in findings if f.priority == RiskLevel.LOW)

        state.atc_report = ATCReport(
            findings=findings,
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            total_findings=len(findings),
            objects_checked=len({f.object_name for f in findings}),
            run_at=datetime.utcnow(),
        )

        state.steps_completed.append("atc_assessment")
        state.current_step = "simplification_analysis"
        log.info("Agent 3 – completed",
                 total_findings=len(findings),
                 critical=critical,
                 high=high)

    except Exception as exc:
        log.error("Agent 3 – failed", error=str(exc))
        state.error_messages.append(f"ATC Assessment: {exc}")

    return state
