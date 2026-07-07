"""
Streamlit Frontend – SAP S/4HANA Migration Assessment Agent
Dark-mode capable, multi-page layout.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SAP Migration Assessment Agent",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inline CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .block-container { padding-top: 1rem; }
    .metric-card {
        background: #1c2028;
        border: 1px solid #2d3748;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .risk-critical { color: #dc2626; font-weight: bold; }
    .risk-high     { color: #f97316; font-weight: bold; }
    .risk-medium   { color: #eab308; font-weight: bold; }
    .risk-low      { color: #22c55e; font-weight: bold; }
    .step-done  { color: #22c55e; }
    .step-pend  { color: #6b7280; }
    .step-curr  { color: #3b82d4; font-weight: bold; }
    h1, h2, h3 { color: #e2e8f0; }
    .stTabs [data-baseweb="tab"] { color: #94a3b8; }
    .stTabs [aria-selected="true"] { color: #3b82d4 !important; border-bottom: 2px solid #3b82d4; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Session state initialisation
# ─────────────────────────────────────────────────────────────────────────────
if "assessment_id" not in st.session_state:
    st.session_state.assessment_id = None
if "state" not in st.session_state:
    st.session_state.state = None
if "running" not in st.session_state:
    st.session_state.running = False
if "logs" not in st.session_state:
    st.session_state.logs = []


def _run_assessment_inline(sap_sid: str, sap_host: str, client: str, use_mock: bool):
    """Run the assessment pipeline directly (no HTTP, for demo mode)."""
    import sys
    import os

    # Ensure imports work when running from frontend/
    root = str(Path(__file__).parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)

    os.environ.setdefault("SAP_USE_MOCK", "true" if use_mock else "false")
    os.environ.setdefault("SAP_HOST", sap_host)
    os.environ.setdefault("SAP_CLIENT", client)
    os.environ.setdefault("REPORTS_OUTPUT_DIR", "output/reports")

    from app.graph.workflow import run_assessment
    from app.models.schemas import SAPSystem

    sap_system = SAPSystem(sid=sap_sid, host=sap_host, client=client)
    return run_assessment(sap_system)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar – SAP Login & Configuration
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/5/59/SAP_2011_logo.svg",
             width=80)
    st.title("Migration Agent")
    st.markdown("---")

    st.subheader("🔐 SAP System Login")
    sap_sid  = st.text_input("System ID (SID)", value="ECC", max_chars=3)
    sap_host = st.text_input("SAP Host", value="sapeccprd.company.com")
    sap_client = st.text_input("Client", value="100", max_chars=3)
    sap_user = st.text_input("RFC User", value="RFC_USER")
    sap_pass = st.text_input("Password", type="password", value="*****")
    use_mock = st.checkbox("Use Mock SAP Data (Demo Mode)", value=True)

    st.markdown("---")
    st.subheader("⚙️ Assessment Options")
    skip_atc = st.checkbox("Skip ATC (faster demo)", value=False)

    st.markdown("---")
    st.caption(f"🟢 Demo Mode: {'ON' if use_mock else 'OFF'}")

    if st.button("🚀 Start Assessment", type="primary", use_container_width=True,
                 disabled=st.session_state.running):
        if not sap_sid or not sap_host:
            st.error("System ID and Host are required.")
        else:
            st.session_state.running = True
            st.session_state.logs = []
            st.session_state.state = None
            st.rerun()

    if st.button("🔄 Reset", use_container_width=True):
        st.session_state.assessment_id = None
        st.session_state.state = None
        st.session_state.running = False
        st.session_state.logs = []
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Main content
# ─────────────────────────────────────────────────────────────────────────────
st.title("🚀 SAP S/4HANA Migration Assessment Agent")
st.markdown("*Autonomous AI-powered assessment of your SAP ECC landscape*")
st.markdown("---")

# ── Running state ─────────────────────────────────────────────────────────────
if st.session_state.running and st.session_state.state is None:
    progress_bar = st.progress(0)
    status_text  = st.empty()

    STEPS = [
        ("🔍 Landscape Discovery",    "Collecting system metadata, versions, components…"),
        ("📦 Custom Code Discovery",  "Scanning Z programs, function modules, classes…"),
        ("🔬 ATC Assessment",         "Running ABAP Test Cockpit checks…"),
        ("📋 Simplification Analysis","Cross-referencing Simplification Database…"),
        ("🔗 Dependency Analysis",    "Building object dependency graph…"),
        ("⚠️  Risk Assessment",        "Calculating migration readiness score…"),
        ("🤖 AI Recommendations",     "Generating fix recommendations via GPT-4o…"),
        ("📘 Runbook Generation",     "Generating migration runbook (PDF/DOCX/MD)…"),
        ("📊 Dashboard Generation",   "Building executive dashboard…"),
    ]

    step_container = st.container()
    with step_container:
        step_placeholders = [st.empty() for _ in STEPS]
        for ph, (title, _) in zip(step_placeholders, STEPS):
            ph.markdown(f"<span class='step-pend'>⏳ {title}</span>", unsafe_allow_html=True)

    with st.spinner("Running assessment pipeline…"):
        try:
            # Show live step updates
            for i, (title, desc) in enumerate(STEPS):
                step_placeholders[i].markdown(
                    f"<span class='step-curr'>▶ {title}</span>", unsafe_allow_html=True)
                status_text.info(f"Step {i+1}/{len(STEPS)}: {desc}")
                progress_bar.progress((i + 0.5) / len(STEPS))
                time.sleep(0.1)  # UI refresh tick

            final_state = _run_assessment_inline(sap_sid, sap_host, sap_client, use_mock)
            st.session_state.state = final_state
            st.session_state.assessment_id = final_state.assessment_id

            for ph, (title, _) in zip(step_placeholders, STEPS):
                ph.markdown(f"<span class='step-done'>✅ {title}</span>", unsafe_allow_html=True)

            progress_bar.progress(1.0)
            status_text.success("✅ Assessment complete!")

        except Exception as exc:
            status_text.error(f"Assessment failed: {exc}")
            st.exception(exc)

    st.session_state.running = False
    st.rerun()

# ── Results ───────────────────────────────────────────────────────────────────
state = st.session_state.state

if state is None:
    st.info("👈 Configure SAP connection in the sidebar and click **Start Assessment**")
    st.markdown("### How it works")
    cols = st.columns(3)
    with cols[0]:
        st.markdown("#### 🔍 Discover")
        st.markdown("Connects to SAP via RFC, collects system metadata, custom code inventory, and ATC findings.")
    with cols[1]:
        st.markdown("#### 🤖 Analyze")
        st.markdown("LangGraph workflow runs 9 specialized agents in sequence. GPT-4o generates actionable recommendations.")
    with cols[2]:
        st.markdown("#### 📊 Report")
        st.markdown("Exports executive dashboard, migration runbook (PDF/DOCX/Markdown), and risk charts.")
    st.stop()

# ── Tabs ─────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "📊 Dashboard",
    "🗺️ Landscape",
    "📦 Custom Code",
    "🔬 ATC Findings",
    "📋 Simplification",
    "⚠️  Risk",
    "🤖 Recommendations",
    "📘 Runbook",
    "📥 Downloads",
    "📋 Logs",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Dashboard
# ─────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("📊 Migration Readiness Dashboard")

    # KPI cards
    col1, col2, col3, col4, col5 = st.columns(5)
    score = state.readiness_score.overall_score if state.readiness_score else 0
    risk = state.readiness_score.risk_level.value.upper() if state.readiness_score else "N/A"
    total_obj = state.custom_code.total_objects if state.custom_code else 0
    total_findings = state.atc_report.total_findings if state.atc_report else 0
    effort = state.readiness_score.estimated_effort_days if state.readiness_score else 0

    col1.metric("🎯 Readiness Score", f"{score:.1f}%")
    col2.metric("⚠️  Risk Level", risk)
    col3.metric("📦 Custom Objects", total_obj)
    col4.metric("🔬 ATC Findings", total_findings)
    col5.metric("📅 Est. Effort", f"{effort} days")

    st.markdown("---")

    # Plotly dashboard
    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=[
            "Readiness Score", "ATC Findings Severity",
            "Custom Code Breakdown", "Simplification Impact",
            "Object Risk Distribution", "Project Timeline",
        ],
        specs=[
            [{"type": "indicator"}, {"type": "bar"},      {"type": "pie"}],
            [{"type": "bar"},       {"type": "pie"},       {"type": "indicator"}],
        ],
    )

    # Gauge
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=score,
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#3b82d4"},
            "steps": [
                {"range": [0, 40],  "color": "#3f1b1b"},
                {"range": [40, 65], "color": "#3f3416"},
                {"range": [65, 100],"color": "#1a3f1e"},
            ],
        },
    ), row=1, col=1)

    # ATC bar
    if state.atc_report:
        atc = state.atc_report
        fig.add_trace(go.Bar(
            x=["Critical", "High", "Medium", "Low"],
            y=[atc.critical_count, atc.high_count, atc.medium_count, atc.low_count],
            marker_color=["#dc2626", "#f97316", "#eab308", "#22c55e"],
            name="ATC",
        ), row=1, col=2)

    # Custom code pie
    if state.custom_code:
        cc = state.custom_code
        fig.add_trace(go.Pie(
            labels=["Programs", "FMs", "Classes", "Tables", "BADIs", "Exits"],
            values=[len(cc.z_programs), len(cc.z_function_modules), len(cc.z_classes),
                    len(cc.custom_tables), len(cc.badis), len(cc.user_exits)],
            hole=0.4,
        ), row=1, col=3)

    # Simplification bar
    if state.simplification_report:
        sr = state.simplification_report
        fig.add_trace(go.Bar(
            x=["Removed TX", "Deprecated FMs", "Deprecated Tables", "UJ", "BP", "ML"],
            y=[len(sr.removed_transactions), len(sr.deprecated_function_modules),
               len(sr.deprecated_tables), len(sr.universal_journal_impacts),
               len(sr.business_partner_items), len(sr.material_ledger_items)],
            marker_color="#7c5cd8",
        ), row=2, col=1)

    # Risk dist pie
    if state.readiness_score and state.readiness_score.object_scores:
        from collections import Counter
        from app.models.schemas import RiskLevel
        dist = Counter(o.risk_level.value for o in state.readiness_score.object_scores)
        fig.add_trace(go.Pie(
            labels=list(dist.keys()),
            values=list(dist.values()),
            marker_colors=["#dc2626", "#f97316", "#eab308", "#22c55e"],
        ), row=2, col=2)

    # Timeline indicator
    weeks = state.runbook.total_estimated_duration_weeks if state.runbook else 0
    fig.add_trace(go.Indicator(
        mode="number",
        value=weeks,
        title={"text": "Project Weeks"},
        number={"suffix": " wks", "font": {"size": 36, "color": "#3b82d4"}},
    ), row=2, col=3)

    fig.update_layout(
        height=600,
        showlegend=False,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#161b22",
        font=dict(color="#e2e8f0", family="Segoe UI, sans-serif"),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: Landscape
# ─────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("🗺️ Landscape Inventory")
    if state.landscape:
        lnd = state.landscape
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### System Information")
            st.table({
                "System ID":      lnd.system_id,
                "Hostname":       lnd.hostname,
                "SAP Version":    lnd.sap_version,
                "Kernel Version": lnd.kernel_version,
                "HANA Version":   lnd.hana_version or "N/A",
            }.items())
        with col2:
            st.markdown("#### Active Clients")
            st.dataframe([{
                "Client": c.get("client", ""), "Description": c.get("description", ""),
            } for c in lnd.active_clients], use_container_width=True)

        st.markdown("#### Installed Components")
        st.dataframe(lnd.installed_components, use_container_width=True)

        st.markdown("#### RFC Destinations")
        st.dataframe(lnd.rfc_destinations, use_container_width=True)

        st.markdown("#### Transport Landscape")
        for sys in lnd.transport_domains:
            st.markdown(f"- `{sys}`")
    else:
        st.warning("Landscape data not available.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: Custom Code
# ─────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("📦 Custom Code Inventory")
    if state.custom_code:
        cc = state.custom_code
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Objects", cc.total_objects)
        c2.metric("Lines of Code", f"{cc.total_lines_of_code:,}")
        c3.metric("Z Programs", len(cc.z_programs))
        c4.metric("Function Modules", len(cc.z_function_modules))

        sub_tabs = st.tabs(["Z Programs", "Function Modules", "Classes", "Tables", "BADIs", "User Exits"])
        with sub_tabs[0]:
            st.dataframe([p.model_dump() for p in cc.z_programs], use_container_width=True)
        with sub_tabs[1]:
            st.dataframe([f.model_dump() for f in cc.z_function_modules], use_container_width=True)
        with sub_tabs[2]:
            st.dataframe([c.model_dump() for c in cc.z_classes], use_container_width=True)
        with sub_tabs[3]:
            st.dataframe([t.model_dump() for t in cc.custom_tables], use_container_width=True)
        with sub_tabs[4]:
            st.dataframe([b.model_dump() for b in cc.badis], use_container_width=True)
        with sub_tabs[5]:
            st.dataframe([u.model_dump() for u in cc.user_exits], use_container_width=True)
    else:
        st.warning("Custom code data not available.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: ATC Findings
# ─────────────────────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("🔬 ATC Assessment Results")
    if state.atc_report:
        atc = state.atc_report
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Findings", atc.total_findings)
        c2.metric("🔴 Critical", atc.critical_count)
        c3.metric("🟠 High", atc.high_count)
        c4.metric("🟡 Medium", atc.medium_count)
        c5.metric("🟢 Low", atc.low_count)

        severity_filter = st.multiselect(
            "Filter by Severity",
            ["critical", "high", "medium", "low"],
            default=["critical", "high"],
        )
        filtered = [f for f in atc.findings if f.priority.value in severity_filter]
        findings_data = [{
            "Object": f.object_name,
            "Type": f.object_type,
            "Severity": f.priority.value.upper(),
            "Category": f.category.value,
            "Message": f.message[:80] + "…" if len(f.message) > 80 else f.message,
            "Line": f.line_number or "N/A",
        } for f in filtered]
        st.dataframe(findings_data, use_container_width=True)
    else:
        st.warning("ATC data not available.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 5: Simplification
# ─────────────────────────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("📋 Simplification Database Analysis")
    if state.simplification_report:
        sr = state.simplification_report
        c1, c2 = st.columns(2)
        c1.metric("Total Impact Items", sr.total_impacts)
        c2.metric("Critical Impacts", sr.critical_impacts)

        sections = {
            "Removed Transactions": sr.removed_transactions,
            "Deprecated Function Modules": sr.deprecated_function_modules,
            "Deprecated Tables": sr.deprecated_tables,
            "Universal Journal": sr.universal_journal_impacts,
            "Business Partner": sr.business_partner_items,
            "Material Ledger": sr.material_ledger_items,
        }
        for title, items in sections.items():
            with st.expander(f"📌 {title} ({len(items)} items)"):
                for item in items:
                    color = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(item.impact.value, "⚪")
                    affected = "✅ Affected" if item.affected_in_system else "➖ Not Detected"
                    st.markdown(f"{color} **{item.object_name}** – {item.title}  \n{affected} | Note: {item.migration_note or 'N/A'}")
    else:
        st.warning("Simplification data not available.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 6: Risk
# ─────────────────────────────────────────────────────────────────────────────
with tabs[5]:
    st.subheader("⚠️ Risk Assessment")
    if state.readiness_score:
        rs = state.readiness_score
        risk_color = {"critical": "risk-critical", "high": "risk-high",
                      "medium": "risk-medium", "low": "risk-low"}.get(rs.risk_level.value, "")
        st.markdown(
            f"### Overall Readiness: **{rs.overall_score:.1f}%** "
            f"<span class='{risk_color}'>({rs.risk_level.value.upper()})</span>",
            unsafe_allow_html=True,
        )

        if rs.critical_objects:
            st.error(f"🚨 Critical Objects ({len(rs.critical_objects)}): " + ", ".join(rs.critical_objects[:10]))
        if rs.high_risk_objects:
            st.warning(f"⚠️ High-Risk Objects ({len(rs.high_risk_objects)}): " + ", ".join(rs.high_risk_objects[:10]))

        st.markdown("#### Top Risky Objects")
        risk_data = [{
            "Object": o.object_name,
            "ATC Score": f"{o.atc_score:.1f}",
            "Total Score": f"{o.total_score:.1f}",
            "Risk Level": o.risk_level.value.upper(),
        } for o in rs.object_scores[:20]]
        st.dataframe(risk_data, use_container_width=True)
    else:
        st.warning("Risk data not available.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 7: Recommendations
# ─────────────────────────────────────────────────────────────────────────────
with tabs[6]:
    st.subheader("🤖 AI Recommendations")
    if state.recommendation_report:
        rr = state.recommendation_report
        st.info(f"📋 {len(rr.recommendations)} recommendations | Total effort: {rr.total_effort_days} days")
        for i, rec in enumerate(rr.recommendations, 1):
            color = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(rec.priority.value, "⚪")
            with st.expander(f"{color} {i}. {rec.object_name} — {rec.problem[:60]}…"):
                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown(f"**🔍 Problem:** {rec.problem}")
                    st.markdown(f"**🌱 Root Cause:** {rec.root_cause}")
                    st.markdown(f"**💼 Business Impact:** {rec.business_impact}")
                    st.markdown(f"**⚙️ Technical Impact:** {rec.technical_impact}")
                with col_r:
                    st.markdown(f"**✅ Recommended Fix:** {rec.recommended_fix}")
                    st.markdown(f"**⏱️ Effort:** {rec.estimated_effort}")
                    st.markdown(f"**👤 Consultant:** {rec.required_consultant}")
                    st.markdown(f"**📅 Duration:** {rec.estimated_duration_days} days")
                    if rec.sap_note:
                        st.markdown(f"**📎 SAP Note:** [{rec.sap_note}](https://launchpad.support.sap.com/#{rec.sap_note})")
    else:
        st.warning("Recommendations not yet generated.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 8: Runbook
# ─────────────────────────────────────────────────────────────────────────────
with tabs[7]:
    st.subheader("📘 Migration Runbook")
    if state.runbook:
        rb = state.runbook
        st.success(f"**{rb.project_name}** — {len(rb.sections)} sections | {rb.total_estimated_duration_weeks} weeks")
        for section in sorted(rb.sections, key=lambda s: s.order):
            with st.expander(f"📌 {section.title}"):
                if section.estimated_duration:
                    st.caption(f"Duration: {section.estimated_duration} | Team: {section.responsible_team or 'TBD'}")
                st.markdown(section.content)
                if section.tasks:
                    st.markdown("**Tasks:**")
                    for task in section.tasks:
                        st.markdown(f"- ☐ {task}")
    else:
        st.warning("Runbook not yet generated.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 9: Downloads
# ─────────────────────────────────────────────────────────────────────────────
with tabs[8]:
    st.subheader("📥 Download Reports")
    output_dir = Path("output/reports")

    if state.runbook:
        rb = state.runbook
        cols = st.columns(3)
        with cols[0]:
            st.markdown("#### 📄 PDF Runbook")
            pdf_p = Path(rb.pdf_path) if rb.pdf_path else None
            if pdf_p and pdf_p.exists():
                with open(pdf_p, "rb") as f:
                    st.download_button("⬇️ Download PDF", f, file_name=pdf_p.name,
                                       mime="application/pdf", use_container_width=True)
            else:
                st.info("PDF not yet available")

        with cols[1]:
            st.markdown("#### 📝 DOCX Runbook")
            docx_p = Path(rb.docx_path) if rb.docx_path else None
            if docx_p and docx_p.exists():
                with open(docx_p, "rb") as f:
                    st.download_button("⬇️ Download DOCX", f, file_name=docx_p.name,
                                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                       use_container_width=True)
            else:
                st.info("DOCX not yet available")

        with cols[2]:
            st.markdown("#### 📋 Markdown Runbook")
            md_p = Path(rb.markdown_path) if rb.markdown_path else None
            if md_p and md_p.exists():
                with open(md_p, "rb") as f:
                    st.download_button("⬇️ Download Markdown", f, file_name=md_p.name,
                                       mime="text/markdown", use_container_width=True)
            else:
                st.info("Markdown not yet available")

    aid_short = state.assessment_id[:8] if state.assessment_id else ""
    dash_path = output_dir / f"dashboard_{aid_short}.html"
    if dash_path.exists():
        st.markdown("#### 📊 Interactive Dashboard (HTML)")
        with open(dash_path, "rb") as f:
            st.download_button("⬇️ Download Dashboard HTML", f, file_name=dash_path.name,
                               mime="text/html", use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 10: Logs
# ─────────────────────────────────────────────────────────────────────────────
with tabs[9]:
    st.subheader("📋 Execution Logs")
    if state:
        log_lines = [f"Assessment ID: {state.assessment_id}",
                     f"Status: {state.status.value}",
                     f"Steps Completed: {', '.join(state.steps_completed)}",
                     f"Current Step: {state.current_step}",
                     ""]
        if state.error_messages:
            log_lines.append("⚠️ ERRORS:")
            log_lines.extend(state.error_messages)
        st.code("\n".join(log_lines), language="text")
    else:
        st.info("No logs yet.")

# Footer
st.markdown("---")
st.markdown("<center><small style='color:#57606a'>Made with IBM Bob · SAP Migration Assessment Agent v1.0.0</small></center>", unsafe_allow_html=True)
