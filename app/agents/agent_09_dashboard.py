"""
Agent 9 – Executive Dashboard Generator
Produces interactive Plotly charts and exports a combined HTML dashboard.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.models.schemas import AgentState, RiskLevel
from app.services import get_logger
from config.settings import get_settings

log = get_logger(__name__)
settings = get_settings()

_OUTPUT = Path(settings.reports_output_dir)


def _gauge_chart(score: float, title: str) -> dict:
    return {
        "type": "indicator",
        "mode": "gauge+number+delta",
        "value": score,
        "title": {"text": title, "font": {"size": 14}},
        "gauge": {
            "axis": {"range": [0, 100]},
            "bar": {"color": "#3b82d4"},
            "steps": [
                {"range": [0, 40],  "color": "#fee2e2"},
                {"range": [40, 65], "color": "#fef3c7"},
                {"range": [65, 100],"color": "#d1fae5"},
            ],
            "threshold": {"line": {"color": "#1f2328", "width": 4}, "value": score},
        },
    }


def build_dashboard_data(state: AgentState) -> dict:
    """Build a JSON-serialisable dashboard data object."""
    dashboard: dict = {
        "assessment_id": state.assessment_id,
        "system_id": state.sap_system.sid,
        "generated_at": datetime.utcnow().isoformat(),
        "charts": {},
    }

    # ── 1. Readiness gauge ───────────────────────────────────────────────────
    score = state.readiness_score.overall_score if state.readiness_score else 0
    dashboard["overall_score"] = score
    dashboard["risk_level"] = state.readiness_score.risk_level.value if state.readiness_score else "unknown"

    # ── 2. ATC summary bar chart ─────────────────────────────────────────────
    if state.atc_report:
        atc = state.atc_report
        dashboard["charts"]["atc_bar"] = {
            "x": ["Critical", "High", "Medium", "Low"],
            "y": [atc.critical_count, atc.high_count, atc.medium_count, atc.low_count],
            "colors": ["#dc2626", "#f97316", "#eab308", "#22c55e"],
        }

    # ── 3. Custom code breakdown ─────────────────────────────────────────────
    if state.custom_code:
        cc = state.custom_code
        dashboard["charts"]["custom_code_pie"] = {
            "labels": ["Z Programs", "Function Modules", "Classes", "Tables", "BADIs", "User Exits"],
            "values": [
                len(cc.z_programs), len(cc.z_function_modules), len(cc.z_classes),
                len(cc.custom_tables), len(cc.badis), len(cc.user_exits),
            ],
        }
        dashboard["custom_code_stats"] = {
            "total_objects": cc.total_objects,
            "total_loc": cc.total_lines_of_code,
        }

    # ── 4. Simplification impact ─────────────────────────────────────────────
    if state.simplification_report:
        sr = state.simplification_report
        dashboard["charts"]["simplif_bar"] = {
            "categories": [
                "Removed TX", "Deprecated FMs", "Deprecated Tables",
                "Compat Views", "Universal Journal", "Business Partner", "Material Ledger"
            ],
            "counts": [
                len(sr.removed_transactions), len(sr.deprecated_function_modules),
                len(sr.deprecated_tables), len(sr.compatibility_views),
                len(sr.universal_journal_impacts), len(sr.business_partner_items),
                len(sr.material_ledger_items),
            ],
        }

    # ── 5. Risk distribution ─────────────────────────────────────────────────
    if state.readiness_score and state.readiness_score.object_scores:
        objs = state.readiness_score.object_scores
        dist = {rl.value: 0 for rl in RiskLevel}
        for o in objs:
            dist[o.risk_level.value] += 1
        dashboard["charts"]["risk_dist"] = dist

    # ── 6. Timeline estimate ─────────────────────────────────────────────────
    if state.runbook:
        dashboard["project_timeline_weeks"] = state.runbook.total_estimated_duration_weeks
        dashboard["runbook_sections"] = len(state.runbook.sections)

    return dashboard


def _export_html_dashboard(dashboard: dict, path: Path) -> str:
    """Write a self-contained HTML dashboard using Plotly CDN (no external assets)."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        import plotly.io as pio

        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=[
                "Migration Readiness Score",
                "ATC Findings by Severity",
                "Custom Code Distribution",
                "Simplification Impact Categories",
                "Object Risk Distribution",
                "Estimated Project Timeline",
            ],
            specs=[
                [{"type": "indicator"}, {"type": "bar"}],
                [{"type": "pie"},       {"type": "bar"}],
                [{"type": "pie"},       {"type": "indicator"}],
            ],
        )

        # Readiness gauge
        score = dashboard.get("overall_score", 0)
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": f"Readiness: {dashboard.get('risk_level','').upper()}"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#3b82d4"},
                "steps": [
                    {"range": [0, 40],  "color": "#fee2e2"},
                    {"range": [40, 65], "color": "#fef3c7"},
                    {"range": [65, 100],"color": "#d1fae5"},
                ],
            },
        ), row=1, col=1)

        # ATC bar
        if "atc_bar" in dashboard.get("charts", {}):
            atc = dashboard["charts"]["atc_bar"]
            fig.add_trace(go.Bar(
                x=atc["x"], y=atc["y"],
                marker_color=atc["colors"],
                name="ATC Findings",
            ), row=1, col=2)

        # Custom code pie
        if "custom_code_pie" in dashboard.get("charts", {}):
            cc = dashboard["charts"]["custom_code_pie"]
            fig.add_trace(go.Pie(
                labels=cc["labels"], values=cc["values"],
                name="Custom Code",
            ), row=2, col=1)

        # Simplification bar
        if "simplif_bar" in dashboard.get("charts", {}):
            sb = dashboard["charts"]["simplif_bar"]
            fig.add_trace(go.Bar(
                x=sb["categories"], y=sb["counts"],
                marker_color="#7c5cd8",
                name="Simplification",
            ), row=2, col=2)

        # Risk distribution pie
        if "risk_dist" in dashboard.get("charts", {}):
            rd = dashboard["charts"]["risk_dist"]
            fig.add_trace(go.Pie(
                labels=list(rd.keys()),
                values=list(rd.values()),
                name="Risk Dist",
                marker_colors=["#dc2626", "#f97316", "#eab308", "#22c55e", "#6b7280"],
            ), row=3, col=1)

        # Project timeline indicator
        weeks = dashboard.get("project_timeline_weeks", 0)
        fig.add_trace(go.Indicator(
            mode="number+delta",
            value=weeks,
            title={"text": "Estimated Weeks"},
            number={"suffix": " wks"},
        ), row=3, col=2)

        fig.update_layout(
            title_text=f"SAP S/4HANA Migration Assessment Dashboard – {dashboard.get('system_id', '')}",
            height=900,
            showlegend=False,
            paper_bgcolor="#ffffff",
            plot_bgcolor="#f7f8fa",
            font=dict(family="Segoe UI, system-ui, sans-serif", size=11),
        )

        html_content = pio.to_html(fig, full_html=True, include_plotlyjs=True)
        path.write_text(html_content, encoding="utf-8")
        log.info("Dashboard HTML exported", path=str(path))
        return str(path)
    except Exception as exc:
        log.warning("Dashboard HTML export failed", error=str(exc))
        return ""


def run_dashboard_generation(state: AgentState) -> AgentState:
    """LangGraph node: generate the executive dashboard."""
    log.info("Agent 9 – Dashboard Generation started", assessment_id=state.assessment_id)
    try:
        _OUTPUT.mkdir(parents=True, exist_ok=True)
        dashboard_data = build_dashboard_data(state)

        # Save raw JSON for API
        json_path = _OUTPUT / f"dashboard_{state.assessment_id[:8]}.json"
        json_path.write_text(json.dumps(dashboard_data, indent=2, default=str), encoding="utf-8")

        # Export interactive HTML
        html_path = _OUTPUT / f"dashboard_{state.assessment_id[:8]}.html"
        _export_html_dashboard(dashboard_data, html_path)

        state.steps_completed.append("dashboard_generation")
        state.current_step = "completed"
        log.info("Agent 9 – completed",
                 json_path=str(json_path),
                 html_path=str(html_path))

    except Exception as exc:
        log.error("Agent 9 – failed", error=str(exc))
        state.error_messages.append(f"Dashboard Generation: {exc}")

    return state
