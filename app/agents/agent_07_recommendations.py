"""
Agent 7 – AI Recommendation Engine
Uses GPT-4o to generate structured recommendations for every critical/high finding.
Falls back to rule-based recommendations when LLM is unavailable.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import List

from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.schemas import (
    AgentState, ATCFinding, Recommendation, RecommendationReport, RiskLevel,
)
from app.prompts.recommendation_prompt import RECOMMENDATION_SYSTEM_PROMPT, build_finding_prompt
from app.services import get_logger, get_llm

log = get_logger(__name__)

_RULE_BASED: dict = {
    "LIST_FROM_MEMORY": Recommendation(
        finding_id="rule-001",
        object_name="LIST_FROM_MEMORY",
        problem="LIST_FROM_MEMORY function module is removed in SAP S/4HANA.",
        root_cause="SAP removed classical list processing APIs in S/4HANA.",
        business_impact="Program will fail at runtime after migration.",
        technical_impact="Compilation error – function module does not exist.",
        recommended_fix="Replace with CL_SALV_TABLE or ALV Grid (cl_gui_alv_grid).",
        estimated_effort="2 hours per occurrence",
        required_consultant="ABAP Developer",
        estimated_duration_days=1,
        priority=RiskLevel.CRITICAL,
        sap_note="2127080",
        best_practice_reference="SAP S/4HANA Simplification List",
    ),
    "REUSE_ALV_GRID_DISPLAY": Recommendation(
        finding_id="rule-002",
        object_name="REUSE_ALV_GRID_DISPLAY",
        problem="REUSE_ALV_GRID_DISPLAY is deprecated and performance-limited.",
        root_cause="Classic ALV function modules are not supported in modern Fiori context.",
        business_impact="Reports will not render in Fiori Launchpad.",
        technical_impact="No direct runtime error but degraded UX and future risk.",
        recommended_fix="Migrate to CL_SALV_TABLE or build Fiori OData-based app.",
        estimated_effort="1 day per report",
        required_consultant="ABAP Developer + Fiori Developer",
        estimated_duration_days=2,
        priority=RiskLevel.HIGH,
        sap_note="2285258",
    ),
    "SQL_INJECTION": Recommendation(
        finding_id="rule-003",
        object_name="DYNAMIC_SQL",
        problem="Dynamic SQL constructed without proper input sanitization.",
        root_cause="Open SQL constructed with string concatenation from user input.",
        business_impact="Security breach risk – unauthorized data access.",
        technical_impact="SQL Injection vulnerability in ABAP program.",
        recommended_fix="Use parameterized queries or CL_ABAP_DYN_PRG for validation.",
        estimated_effort="4 hours per occurrence",
        required_consultant="ABAP Security Consultant",
        estimated_duration_days=1,
        priority=RiskLevel.CRITICAL,
        sap_note="1520356",
    ),
}


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _llm_recommend(finding: ATCFinding, llm) -> Recommendation:
    prompt = build_finding_prompt(finding)
    response = llm.invoke([
        {"role": "system", "content": RECOMMENDATION_SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ])
    content = response.content.strip()
    # Extract JSON block
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    data = json.loads(content)
    return Recommendation(
        finding_id=f"llm-{finding.check_id[:20]}",
        object_name=finding.object_name,
        **{k: v for k, v in data.items() if k in Recommendation.model_fields},
        priority=finding.priority,
    )


def _rule_based_recommend(finding: ATCFinding) -> Recommendation:
    """Fallback: pick closest rule-based recommendation."""
    for key, rec in _RULE_BASED.items():
        if key.upper() in finding.message.upper() or key.upper() in finding.check_title.upper():
            return rec.model_copy(update={
                "finding_id": f"rule-{finding.check_id[:20]}",
                "object_name": finding.object_name,
                "priority": finding.priority,
            })
    # Generic fallback
    return Recommendation(
        finding_id=f"rule-generic-{finding.object_name}",
        object_name=finding.object_name,
        problem=f"ATC finding: {finding.check_title}",
        root_cause="Review ATC check documentation for root cause.",
        business_impact="Potential runtime failure or degraded functionality after S/4HANA migration.",
        technical_impact=finding.message,
        recommended_fix="Review SAP simplification item and refactor accordingly.",
        estimated_effort="To be estimated during detailed analysis",
        required_consultant="ABAP Developer",
        estimated_duration_days=1,
        priority=finding.priority,
    )


def run_recommendation_generation(state: AgentState) -> AgentState:
    """LangGraph node: generate AI recommendations for all critical/high findings."""
    log.info("Agent 7 – Recommendation Engine started", assessment_id=state.assessment_id)
    try:
        recommendations: List[Recommendation] = []

        target_findings: List[ATCFinding] = []
        if state.atc_report:
            target_findings = [
                f for f in state.atc_report.findings
                if f.priority in (RiskLevel.CRITICAL, RiskLevel.HIGH)
            ][:20]  # Cap at 20 to control token costs

        try:
            llm = get_llm()
            use_llm = bool(llm.openai_api_key and "dummy" not in str(llm.openai_api_key))
        except Exception:
            use_llm = False

        for finding in target_findings:
            try:
                if use_llm:
                    rec = _llm_recommend(finding, llm)
                else:
                    rec = _rule_based_recommend(finding)
                recommendations.append(rec)
            except Exception as exc:
                log.warning("Recommendation fallback for finding",
                            finding=finding.object_name, error=str(exc))
                recommendations.append(_rule_based_recommend(finding))

        # Also add simplification-based recommendations
        if state.simplification_report:
            for item in (state.simplification_report.business_partner_items +
                         state.simplification_report.universal_journal_impacts):
                if item.affected_in_system and item.impact == RiskLevel.CRITICAL:
                    recommendations.append(Recommendation(
                        finding_id=f"simplif-{item.item_id}",
                        object_name=item.object_name,
                        problem=item.title,
                        root_cause=f"SAP S/4HANA Simplification: {item.category}",
                        business_impact="Mandatory migration step – go-live blocker if not addressed.",
                        technical_impact=item.description,
                        recommended_fix=item.migration_note or "Follow SAP migration guide.",
                        estimated_effort="Project team alignment required",
                        required_consultant="SAP Functional Consultant + BASIS",
                        estimated_duration_days=5,
                        priority=RiskLevel.CRITICAL,
                    ))

        total_effort = sum(r.estimated_duration_days for r in recommendations)

        state.recommendation_report = RecommendationReport(
            recommendations=recommendations,
            total_effort_days=total_effort,
            generated_at=datetime.utcnow(),
        )

        state.steps_completed.append("recommendation_generation")
        state.current_step = "runbook_generation"
        log.info("Agent 7 – completed",
                 total_recommendations=len(recommendations),
                 total_effort_days=total_effort)

    except Exception as exc:
        log.error("Agent 7 – failed", error=str(exc))
        state.error_messages.append(f"Recommendation Generation: {exc}")

    return state
