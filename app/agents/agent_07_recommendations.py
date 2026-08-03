"""
Agent 7 – AI Recommendation Engine
Uses IBM Consulting Advantage LLM to generate structured recommendations for every
critical/high finding. Falls back to rule-based recommendations when LLM is unavailable.
Exports results to Excel (.xlsx) and CSV for download.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import List

from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.schemas import (
    AgentState, ATCFinding, Recommendation, RecommendationReport, RiskLevel,
)
from app.prompts.recommendation_prompt import RECOMMENDATION_SYSTEM_PROMPT, build_finding_prompt
from app.services import get_logger, get_llm
from app.services.llm_client import is_llm_available
from config.settings import get_settings

_settings = get_settings()
_OUTPUT = Path(_settings.reports_output_dir)

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


# ── Export helpers ────────────────────────────────────────────────────────────

_COLUMNS = [
    "finding_id", "priority", "object_name", "problem", "root_cause",
    "business_impact", "technical_impact", "recommended_fix",
    "estimated_effort", "estimated_duration_days", "required_consultant",
    "sap_note", "best_practice_reference",
]


def _export_excel(recommendations: List[Recommendation], path: Path) -> str:
    """Export recommendations to a formatted .xlsx file."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "LLM Recommendations"

        # ── Colour palette ──────────────────────────────────────────────────
        PRIORITY_FILL = {
            "critical": PatternFill("solid", fgColor="7F1D1D"),
            "high":     PatternFill("solid", fgColor="7C2D12"),
            "medium":   PatternFill("solid", fgColor="713F12"),
            "low":      PatternFill("solid", fgColor="14532D"),
        }
        PRIORITY_FONT = {
            "critical": Font(bold=True, color="FCA5A5"),
            "high":     Font(bold=True, color="FDBA74"),
            "medium":   Font(bold=True, color="FDE047"),
            "low":      Font(bold=True, color="86EFAC"),
        }
        HDR_FILL = PatternFill("solid", fgColor="1E3A5F")
        HDR_FONT = Font(bold=True, color="93C5FD")
        thin = Side(style="thin", color="2D3748")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        # ── Header row ──────────────────────────────────────────────────────
        headers = [c.replace("_", " ").title() for c in _COLUMNS]
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.fill = HDR_FILL
            cell.font = HDR_FONT
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
            cell.border = border
        ws.row_dimensions[1].height = 22

        # ── Data rows ───────────────────────────────────────────────────────
        for row_idx, rec in enumerate(recommendations, 2):
            data = rec.model_dump()
            priority = data.get("priority", "low")
            for col_idx, col_name in enumerate(_COLUMNS, 1):
                value = data.get(col_name, "")
                if hasattr(value, "value"):   # Enum → string
                    value = value.value
                cell = ws.cell(row=row_idx, column=col_idx, value=str(value) if value else "")
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                cell.border = border
                if col_idx == 2:              # Priority column gets colour coding
                    cell.fill = PRIORITY_FILL.get(str(priority), PatternFill())
                    cell.font = PRIORITY_FONT.get(str(priority), Font())

        # ── Column widths ───────────────────────────────────────────────────
        col_widths = [18, 12, 22, 40, 40, 40, 40, 50, 20, 12, 28, 14, 30]
        for i, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

        # ── Summary sheet ───────────────────────────────────────────────────
        ws2 = wb.create_sheet("Summary")
        from collections import Counter
        priority_counts = Counter(
            (rec.priority.value if hasattr(rec.priority, "value") else rec.priority)
            for rec in recommendations
        )
        ws2.append(["Priority", "Count"])
        for p in ["critical", "high", "medium", "low"]:
            ws2.append([p.upper(), priority_counts.get(p, 0)])
        ws2.append([])
        ws2.append(["Total Recommendations", len(recommendations)])
        ws2.append(["Total Effort (days)", sum(r.estimated_duration_days for r in recommendations)])
        ws2.append(["Generated By", "IBM Consulting Advantage – meta-llama/llama-4-maverick-17b-instruct-fp8"])
        ws2.append(["Generated At", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")])

        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(str(path))
        return str(path)
    except Exception as exc:
        log.warning("Excel export failed", error=str(exc))
        return ""


def _export_csv(recommendations: List[Recommendation], path: Path) -> str:
    """Export recommendations to a UTF-8 CSV file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_COLUMNS)
            writer.writeheader()
            for rec in recommendations:
                data = rec.model_dump()
                row = {}
                for col in _COLUMNS:
                    val = data.get(col, "")
                    row[col] = val.value if hasattr(val, "value") else (str(val) if val else "")
                writer.writerow(row)
        return str(path)
    except Exception as exc:
        log.warning("CSV export failed", error=str(exc))
        return ""


# ── Main agent node ───────────────────────────────────────────────────────────

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
            use_llm = is_llm_available()
            llm = get_llm() if use_llm else None
        except Exception:
            use_llm = False
            llm = None

        log.info("Agent 7 – LLM status", use_llm=use_llm,
                 backend=_settings.llm_backend,
                 model=_settings.ica_model if _settings.llm_backend == "ica" else _settings.openai_model)

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

        # ── Export to Excel + CSV ─────────────────────────────────────────
        _OUTPUT.mkdir(parents=True, exist_ok=True)
        aid = state.assessment_id[:8]
        excel_path = _export_excel(recommendations, _OUTPUT / f"recommendations_{aid}.xlsx")
        csv_path   = _export_csv(recommendations,   _OUTPUT / f"recommendations_{aid}.csv")

        state.recommendation_report = RecommendationReport(
            recommendations=recommendations,
            total_effort_days=total_effort,
            generated_at=datetime.utcnow(),
            excel_path=excel_path or None,
            csv_path=csv_path or None,
        )

        state.steps_completed.append("recommendation_generation")
        state.current_step = "runbook_generation"
        log.info("Agent 7 – completed",
                 total_recommendations=len(recommendations),
                 total_effort_days=total_effort,
                 excel_path=excel_path,
                 csv_path=csv_path)

    except Exception as exc:
        log.error("Agent 7 – failed", error=str(exc))
        state.error_messages.append(f"Recommendation Generation: {exc}")

    return state
