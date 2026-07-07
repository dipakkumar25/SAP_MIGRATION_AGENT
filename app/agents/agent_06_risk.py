"""
Agent 6 – Risk Assessment
Calculates a migration readiness score (0–100) using a weighted formula.
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from app.models.schemas import (
    AgentState, MigrationReadinessScore, RiskLevel, RiskScore,
)
from app.services import get_logger

log = get_logger(__name__)

# ── Scoring weights (sum to 1.0) ─────────────────────────────────────────────
W_ATC         = 0.30
W_COMPLEXITY  = 0.15
W_DEPRECATED  = 0.25
W_MODS        = 0.10
W_DEPENDENCY  = 0.10
W_PERFORMANCE = 0.05
W_UNUSED      = 0.05


def _risk_from_score(score: float) -> RiskLevel:
    if score >= 70:
        return RiskLevel.CRITICAL
    if score >= 50:
        return RiskLevel.HIGH
    if score >= 25:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _readiness_from_risk_score(aggregate_risk: float) -> float:
    """Convert aggregate risk (higher=worse) to readiness percentage (higher=better)."""
    return max(0.0, min(100.0, 100.0 - aggregate_risk))


def _calc_atc_score(state: AgentState) -> float:
    if not state.atc_report:
        return 0.0
    total = max(state.atc_report.total_findings, 1)
    weighted = (
        state.atc_report.critical_count * 10 +
        state.atc_report.high_count     *  5 +
        state.atc_report.medium_count   *  2 +
        state.atc_report.low_count      *  0.5
    )
    return min(100.0, weighted / total * 10)


def _calc_deprecated_score(state: AgentState) -> float:
    if not state.simplification_report:
        return 0.0
    affected_critical = sum(
        1 for item in (
            state.simplification_report.deprecated_function_modules +
            state.simplification_report.deprecated_tables +
            state.simplification_report.universal_journal_impacts +
            state.simplification_report.business_partner_items
        )
        if item.affected_in_system and item.impact in (RiskLevel.CRITICAL, RiskLevel.HIGH)
    )
    return min(100.0, affected_critical * 8.0)


def _calc_complexity_score(state: AgentState) -> float:
    if not state.custom_code:
        return 0.0
    total_loc = state.custom_code.total_lines_of_code
    if total_loc < 5_000:
        return 10.0
    if total_loc < 20_000:
        return 30.0
    if total_loc < 100_000:
        return 60.0
    return 85.0


def _calc_dependency_score(state: AgentState) -> float:
    if not state.dependency_graph:
        return 0.0
    depth = state.dependency_graph.max_depth
    return min(100.0, depth * 12.0)


def run_risk_assessment(state: AgentState) -> AgentState:
    """LangGraph node: compute per-object risk scores and overall readiness."""
    log.info("Agent 6 – Risk Assessment started", assessment_id=state.assessment_id)
    try:
        atc_score        = _calc_atc_score(state)
        deprecated_score = _calc_deprecated_score(state)
        complexity_score = _calc_complexity_score(state)
        dependency_score = _calc_dependency_score(state)

        aggregate_risk = (
            atc_score        * W_ATC +
            complexity_score * W_COMPLEXITY +
            deprecated_score * W_DEPRECATED +
            dependency_score * W_DEPENDENCY
        )

        overall_readiness = _readiness_from_risk_score(aggregate_risk)
        overall_risk_level = _risk_from_score(aggregate_risk)

        # Per-object scores (top offenders from ATC)
        object_scores: List[RiskScore] = []
        if state.atc_report:
            from collections import Counter
            obj_severity: dict = {}
            for f in state.atc_report.findings:
                key = f.object_name
                points = {"critical": 10, "high": 5, "medium": 2, "low": 0.5}.get(f.priority.value, 0)
                obj_severity[key] = obj_severity.get(key, 0) + points

            for obj_name, raw_score in sorted(obj_severity.items(), key=lambda x: -x[1])[:30]:
                norm = min(100.0, raw_score)
                object_scores.append(RiskScore(
                    object_name=obj_name,
                    object_type="PROG",
                    atc_score=norm,
                    total_score=norm,
                    risk_level=_risk_from_score(norm),
                ))

        critical_objs = [s.object_name for s in object_scores if s.risk_level == RiskLevel.CRITICAL]
        high_objs     = [s.object_name for s in object_scores if s.risk_level == RiskLevel.HIGH]

        # Effort estimation: roughly 2 days per critical object, 1 per high
        effort_days = len(critical_objs) * 2 + len(high_objs) * 1 + 30  # baseline

        state.readiness_score = MigrationReadinessScore(
            overall_score=round(overall_readiness, 1),
            risk_level=overall_risk_level,
            object_scores=object_scores,
            critical_objects=critical_objs,
            high_risk_objects=high_objs,
            estimated_effort_days=effort_days,
            assessed_at=datetime.utcnow(),
        )

        state.steps_completed.append("risk_assessment")
        state.current_step = "recommendation_generation"
        log.info("Agent 6 – completed",
                 overall_readiness=overall_readiness,
                 risk_level=overall_risk_level,
                 effort_days=effort_days)

    except Exception as exc:
        log.error("Agent 6 – failed", error=str(exc))
        state.error_messages.append(f"Risk Assessment: {exc}")

    return state
