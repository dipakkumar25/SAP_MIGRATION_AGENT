"""
Streamlit Frontend – SAP MM Module Migration Assessment Dashboard
Focused on SAP MM (Materials Management): Procurement, Inventory,
Warehouse Management, Material Master, Goods Movements, and MRP.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SAP MM Migration Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Layout ── */
    .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }

    /* ── KPI card ── */
    .kpi-card {
        background: #1c2028;
        border: 1px solid #2d3748;
        border-radius: 10px;
        padding: 18px 14px;
        text-align: center;
        min-height: 100px;
    }
    .kpi-label { color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
    .kpi-value { color: #e2e8f0; font-size: 1.8rem; font-weight: 700; line-height: 1.1; }
    .kpi-sub   { color: #57606a; font-size: 0.72rem; margin-top: 4px; }

    /* ── Risk badges ── */
    .badge-critical { background:#7f1d1d; color:#fca5a5; border-radius:4px; padding:2px 8px; font-size:0.75rem; font-weight:600; }
    .badge-high     { background:#7c2d12; color:#fdba74; border-radius:4px; padding:2px 8px; font-size:0.75rem; font-weight:600; }
    .badge-medium   { background:#713f12; color:#fde047; border-radius:4px; padding:2px 8px; font-size:0.75rem; font-weight:600; }
    .badge-low      { background:#14532d; color:#86efac; border-radius:4px; padding:2px 8px; font-size:0.75rem; font-weight:600; }

    /* ── Section heading ── */
    .section-title {
        color: #94a3b8;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        border-bottom: 1px solid #2d3748;
        padding-bottom: 4px;
        margin-bottom: 10px;
    }

    /* ── MM process area pill ── */
    .mm-pill {
        display: inline-block;
        background: #1e3a5f;
        color: #93c5fd;
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 0.72rem;
        margin: 2px 3px 2px 0;
    }

    /* ── Step tracker ── */
    .step-done { color: #22c55e; }
    .step-pend { color: #4b5563; }
    .step-curr { color: #3b82f6; font-weight: bold; }

    /* ── Tab styling ── */
    .stTabs [data-baseweb="tab"] { color: #94a3b8; font-size: 0.85rem; }
    .stTabs [aria-selected="true"] { color: #3b82f6 !important; border-bottom: 2px solid #3b82f6; }

    /* ── Headings ── */
    h1, h2, h3, h4 { color: #e2e8f0; }

    /* ── Alert stripe ── */
    .alert-critical { border-left: 4px solid #dc2626; background:#1c1010; padding: 8px 12px; border-radius:0 6px 6px 0; margin-bottom:6px; }
    .alert-high     { border-left: 4px solid #f97316; background:#1c1208; padding: 8px 12px; border-radius:0 6px 6px 0; margin-bottom:6px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Constants – SAP MM process areas & their key objects
# ─────────────────────────────────────────────────────────────────────────────
MM_PROCESS_AREAS = {
    "Procurement (P2P)": {
        "icon": "🛒",
        "desc": "Purchase Requisitions, Purchase Orders, Supplier Management",
        "key_tables":  ["EKKO", "EKPO", "EKET", "EKKN", "EINA", "EINE"],
        "key_tx":      ["ME21N", "ME22N", "ME23N", "ME51N", "ME2M", "ME2N"],
        "s4_changes":  ["ME2M replaced by Manage Purchase Orders Fiori app",
                        "EKPO compatibility view – use CDS C_PurchaseOrderItemTP",
                        "SRM/EBP replaced by SAP Ariba or Central Purchasing"],
    },
    "Inventory Management": {
        "icon": "📦",
        "desc": "Goods Receipts, Goods Issues, Stock Transfers, Physical Inventory",
        "key_tables":  ["MSEG", "MKPF", "MARD", "MCHB", "MARC", "MARA"],
        "key_tx":      ["MIGO", "MB51", "MB52", "MB1A", "MB1B", "MI07"],
        "s4_changes":  ["MARA material master restructured – new S/4HANA fields",
                        "MARC plant data extended with additional fields",
                        "MB52 warehouse stocks – use Manage Inventory Fiori app",
                        "BAPI_GOODSMVT_CREATE API enhanced in S/4HANA"],
    },
    "Warehouse Management (WM→EWM)": {
        "icon": "🏭",
        "desc": "Transfer Orders, Storage Bins, Physical Inventory in WM",
        "key_tables":  ["LTAP", "LTBK", "LGPLA", "LQUA", "T301"],
        "key_tx":      ["LT01", "LT0A", "LI01", "LL01", "LT21"],
        "s4_changes":  ["Classic WM deprecated – migrate to Embedded EWM",
                        "Transfer order logic must be redesigned in EWM",
                        "Lean WM available as compatibility option (limited)"],
    },
    "Material Master": {
        "icon": "📋",
        "desc": "Material Types, Classification, Valuation, MRP Data",
        "key_tables":  ["MARA", "MARC", "MARD", "MBEW", "MLAN", "MAKT"],
        "key_tx":      ["MM01", "MM02", "MM60", "CKMVFM", "MR21"],
        "s4_changes":  ["BAPI_MATERIAL_SAVEDATA – use API_PRODUCT_SRV OData",
                        "MR21 price change – restricted, use Fiori app",
                        "Material Ledger activation mandatory for all plants",
                        "MBEW valuation data restructured with mandatory ML"],
    },
    "Invoice Verification (LIV)": {
        "icon": "🧾",
        "desc": "Logistics Invoice Verification, GR-Based IV, ERS",
        "key_tables":  ["RBKP", "RSEG", "RBCO", "BSIK", "BSAK"],
        "key_tx":      ["MIRO", "MR8M", "MRRL", "MR11"],
        "s4_changes":  ["RBKP/RSEG read via ACDOCA in Universal Journal",
                        "Vendor data mandatory as Business Partner (FLBP)",
                        "ERS (Evaluated Receipt Settlement) process unchanged"],
    },
    "MRP & Planning": {
        "icon": "📈",
        "desc": "Material Requirements Planning, Demand Management, Planned Orders",
        "key_tables":  ["PLAF", "MDBS", "MDKP", "RESB", "PBED"],
        "key_tx":      ["MD01", "MD02", "MD04", "MD06", "MD11"],
        "s4_changes":  ["MRP Live (S/4HANA MRP) replaces classic MRP transaction MD01",
                        "pMRP (Predictive MRP) available as new capability",
                        "Custom MRP user exits must be re-evaluated for MRP Live"],
    },
}

MM_CRITICAL_SIMPLIFICATIONS = [
    {"object": "BAPI_GOODSMVT_CREATE",  "area": "Inventory Mgmt",  "note": "API signature changed – review all GR/GI postings",        "impact": "critical"},
    {"object": "BAPI_MATERIAL_SAVEDATA","area": "Material Master", "note": "Replace with API_PRODUCT_SRV OData service",               "impact": "critical"},
    {"object": "BAPI_PO_CREATE1",        "area": "Procurement",    "note": "Enhanced MM_PO_* API recommended in S/4HANA",              "impact": "high"},
    {"object": "MARC",                   "area": "Material Master", "note": "Plant data structure extended – custom reads may break",   "impact": "medium"},
    {"object": "MARA",                   "area": "Material Master", "note": "New product classification fields in S/4HANA",             "impact": "medium"},
    {"object": "EKPO_VIEW",              "area": "Procurement",    "note": "Use CDS view C_PurchaseOrderItemTP instead",               "impact": "medium"},
    {"object": "MB52",                   "area": "Inventory Mgmt",  "note": "Use Manage Inventory Fiori app",                          "impact": "low"},
    {"object": "ME2M",                   "area": "Procurement",    "note": "Use Manage Purchase Orders Fiori app",                    "impact": "medium"},
    {"object": "Material Ledger",        "area": "Valuation",      "note": "Mandatory for all plants before migration",               "impact": "high"},
    {"object": "MBEW",                   "area": "Valuation",      "note": "Valuation restructured with mandatory ML activation",     "impact": "high"},
    {"object": "MR21",                   "area": "Material Master", "note": "Price change restricted – use Fiori equivalent",         "impact": "medium"},
    {"object": "Classic WM (LT*)",       "area": "WM → EWM",       "note": "Classic WM deprecated – migrate to Embedded EWM",        "impact": "critical"},
]

# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
for _k, _v in [
    ("assessment_id", None),
    ("state", None),
    ("running", False),
    ("mm_data", None),
    ("selected_system", None),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ─────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────────────────────

def _badge(level: str) -> str:
    return f"<span class='badge-{level}'>{level.upper()}</span>"


def _risk_color(level: str) -> str:
    return {"critical": "#dc2626", "high": "#f97316", "medium": "#eab308", "low": "#22c55e"}.get(level, "#94a3b8")


def _kpi(label: str, value: str, sub: str = "") -> str:
    return f"""
    <div class='kpi-card'>
        <div class='kpi-label'>{label}</div>
        <div class='kpi-value'>{value}</div>
        {'<div class="kpi-sub">' + sub + '</div>' if sub else ''}
    </div>"""


def _load_mm_sample() -> list:
    """Load the MM sample data file."""
    p = Path(__file__).parent.parent / "sample_data" / "sample_mm_assessments.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return []


def _run_live_assessment(sap_sid: str, sap_host: str, client: str, use_mock: bool):
    """Run the full LangGraph pipeline and return AgentState."""
    import sys, os
    root = str(Path(__file__).parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ.setdefault("SAP_USE_MOCK", "true" if use_mock else "false")
    os.environ.setdefault("SAP_HOST", sap_host)
    os.environ.setdefault("SAP_CLIENT", client)
    os.environ.setdefault("REPORTS_OUTPUT_DIR", "output/reports")
    from app.graph.workflow import run_assessment
    from app.models.schemas import SAPSystem
    return run_assessment(SAPSystem(sid=sap_sid, host=sap_host, client=client))


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📦 SAP MM Migration")
    st.markdown("<div class='section-title'>Module Focus</div>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:0.8rem;color:#94a3b8;line-height:1.7'>
    ✅ Procurement (P2P)<br>
    ✅ Inventory Management<br>
    ✅ Warehouse Management<br>
    ✅ Material Master<br>
    ✅ Invoice Verification<br>
    ✅ MRP & Planning
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    mode = st.radio(
        "Assessment Mode",
        ["📂 Load MM Sample Data", "🚀 Run Live Assessment"],
        index=0,
    )

    if mode == "📂 Load MM Sample Data":
        mm_systems = _load_mm_sample()
        if mm_systems:
            sys_labels = [f"{s['sap_system']['sid']} – {s['sap_system']['description'][:40]}" for s in mm_systems]
            selected_idx = st.selectbox("Select MM System", range(len(sys_labels)), format_func=lambda i: sys_labels[i])
            if st.button("📂 Load System", type="primary", use_container_width=True):
                st.session_state.mm_data = mm_systems[selected_idx]
                st.session_state.state = None
                st.session_state.selected_system = mm_systems[selected_idx]["sap_system"]["sid"]
                st.rerun()
        else:
            st.warning("sample_mm_assessments.json not found.")

    else:
        st.markdown("<div class='section-title'>SAP Connection</div>", unsafe_allow_html=True)
        sap_sid    = st.text_input("System ID (SID)", value="MM1", max_chars=5)
        sap_host   = st.text_input("SAP Host", value="sapmmprd.company.com")
        sap_client = st.text_input("Client", value="100", max_chars=3)
        st.text_input("RFC User", value="RFC_MM_USER")
        st.text_input("Password", type="password", value="*****")
        use_mock   = st.checkbox("Demo Mode (Mock SAP Data)", value=True)

        if st.button("🚀 Run Assessment", type="primary", use_container_width=True,
                     disabled=st.session_state.running):
            st.session_state.running = True
            st.session_state.mm_data = None
            st.session_state.state = None
            st.rerun()

    st.markdown("---")
    if st.button("🔄 Reset Dashboard", use_container_width=True):
        for k in ["assessment_id", "state", "running", "mm_data", "selected_system"]:
            st.session_state[k] = None if k != "running" else False
        st.rerun()

    st.markdown("---")
    st.markdown("<div style='font-size:0.7rem;color:#4b5563'>SAP MM Migration Agent v2.0<br>Powered by LangGraph + IBM Consulting Advantage</div>",
                unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Live assessment runner
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.running and st.session_state.state is None:
    st.title("📦 SAP MM Migration Assessment")
    pb = st.progress(0)
    status = st.empty()
    STEPS = [
        ("🔍 Landscape Discovery",    "Collecting system metadata, components, versions…"),
        ("📦 Custom Code Discovery",  "Scanning MM Z programs, BADIs, user exits…"),
        ("🔬 ATC Assessment",         "Running ABAP Test Cockpit on MM objects…"),
        ("📋 Simplification Analysis","Cross-referencing MM Simplification items…"),
        ("🔗 Dependency Analysis",    "Mapping MM object dependencies…"),
        ("⚠️  Risk Assessment",        "Calculating MM migration readiness score…"),
        ("🤖 AI Recommendations",     "Generating MM-specific fix recommendations…"),
        ("📘 Runbook Generation",     "Building MM migration runbook…"),
        ("📊 Dashboard Generation",   "Finalising executive dashboard…"),
    ]
    placeholders = [st.empty() for _ in STEPS]
    for ph, (t, _) in zip(placeholders, STEPS):
        ph.markdown(f"<span class='step-pend'>⏳ {t}</span>", unsafe_allow_html=True)

    with st.spinner("Running MM assessment pipeline…"):
        try:
            for i, (title, desc) in enumerate(STEPS):
                placeholders[i].markdown(f"<span class='step-curr'>▶ {title}</span>", unsafe_allow_html=True)
                status.info(f"Step {i+1}/{len(STEPS)}: {desc}")
                pb.progress((i + 0.5) / len(STEPS))
                time.sleep(0.08)
            final_state = _run_live_assessment(sap_sid, sap_host, sap_client, use_mock)
            st.session_state.state = final_state
            st.session_state.assessment_id = final_state.assessment_id
            for ph, (t, _) in zip(placeholders, STEPS):
                ph.markdown(f"<span class='step-done'>✅ {t}</span>", unsafe_allow_html=True)
            pb.progress(1.0)
            status.success("✅ MM Assessment complete!")
        except Exception as exc:
            status.error(f"Assessment failed: {exc}")
            st.exception(exc)
    st.session_state.running = False
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Landing page (nothing loaded yet)
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.mm_data is None and st.session_state.state is None:
    st.title("📦 SAP MM Migration Assessment Dashboard")
    st.markdown("*Focused analysis for SAP Materials Management → S/4HANA migration*")
    st.markdown("---")

    # MM module overview cards
    cols = st.columns(3)
    areas = list(MM_PROCESS_AREAS.items())
    for i, (area, meta) in enumerate(areas):
        with cols[i % 3]:
            st.markdown(f"""
            <div class='kpi-card' style='text-align:left;min-height:160px'>
                <div style='font-size:1.5rem'>{meta['icon']}</div>
                <div style='color:#e2e8f0;font-weight:600;margin:4px 0'>{area}</div>
                <div style='color:#94a3b8;font-size:0.78rem'>{meta['desc']}</div>
                <div style='margin-top:8px'>
                    {''.join(f"<span class='mm-pill'>{tx}</span>" for tx in meta['key_tx'][:3])}
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("")

    st.markdown("---")
    st.markdown("### Critical S/4HANA Changes in SAP MM")
    cols2 = st.columns([1, 2, 2, 1])
    cols2[0].markdown("**Object**")
    cols2[1].markdown("**Migration Note**")
    cols2[2].markdown("**Area**")
    cols2[3].markdown("**Impact**")
    for item in MM_CRITICAL_SIMPLIFICATIONS:
        c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
        c1.markdown(f"`{item['object']}`")
        c2.markdown(f"<span style='font-size:0.82rem'>{item['note']}</span>", unsafe_allow_html=True)
        c3.markdown(f"<span class='mm-pill'>{item['area']}</span>", unsafe_allow_html=True)
        c4.markdown(_badge(item["impact"]), unsafe_allow_html=True)

    st.markdown("---")
    st.info("👈 Select an MM system from the sidebar to load assessment data, or run a live assessment.")
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Resolve data source – either sample JSON or live AgentState
# ─────────────────────────────────────────────────────────────────────────────
_sample = st.session_state.mm_data        # dict from JSON
_live   = st.session_state.state          # AgentState object

def _g(path: str, default=None):
    """Safely read a dot-path from the sample dict."""
    try:
        val = _sample
        for k in path.split("."):
            val = val[k]
        return val if val is not None else default
    except (KeyError, TypeError):
        return default


# Unified accessors – work with both sample dict and live AgentState
if _sample:
    sys_sid         = _g("sap_system.sid", "MM?")
    sys_desc        = _g("sap_system.description", "")
    sys_version     = _g("sap_system.sap_version", "N/A")
    sys_kernel      = _g("sap_system.kernel_version", "N/A")
    sys_hana        = _g("sap_system.hana_version") or "Not on HANA"
    sys_client      = _g("sap_system.client", "100")
    sys_host        = _g("sap_system.host", "")
    landscape       = _g("sap_system.landscape", {})

    total_obj       = _g("custom_code_summary.total_objects", 0)
    total_loc       = _g("custom_code_summary.total_lines_of_code", 0)
    z_programs      = _g("custom_code_summary.z_programs", 0)
    func_mods       = _g("custom_code_summary.function_modules", 0)
    classes         = _g("custom_code_summary.classes", 0)
    custom_tables   = _g("custom_code_summary.custom_tables", 0)
    badis           = _g("custom_code_summary.badis", 0)
    user_exits      = _g("custom_code_summary.user_exits", 0)
    enh_spots       = _g("custom_code_summary.enhancement_spots", 0)
    modules_covered = _g("custom_code_summary.modules_covered", [])

    atc_total       = _g("atc_summary.total_findings", 0)
    atc_critical    = _g("atc_summary.critical", 0)
    atc_high        = _g("atc_summary.high", 0)
    atc_medium      = _g("atc_summary.medium", 0)
    atc_low         = _g("atc_summary.low", 0)
    atc_checked     = _g("atc_summary.objects_checked", 0)
    atc_categories  = _g("atc_summary.categories", {})

    simplif_total   = _g("simplification_summary.total_items", 0)
    simplif_removed = _g("simplification_summary.removed_transactions", 0)
    simplif_fms     = _g("simplification_summary.deprecated_fms", 0)
    simplif_tabs    = _g("simplification_summary.deprecated_tables", 0)
    simplif_compat  = _g("simplification_summary.compatibility_views", 0)
    simplif_uj      = _g("simplification_summary.universal_journal_impacts", 0)
    simplif_bp      = _g("simplification_summary.business_partner_items", 0)
    simplif_ml      = _g("simplification_summary.material_ledger_items", 0)

    readiness_score = _g("risk_summary.overall_score", 0)
    risk_level      = _g("risk_summary.risk_level", "unknown")
    effort_days     = _g("risk_summary.estimated_effort_days", 0)
    critical_areas  = _g("risk_summary.critical_areas", [])

else:  # live AgentState
    sys_sid         = _live.sap_system.sid
    sys_desc        = _live.sap_system.description or ""
    sys_version     = _live.landscape.sap_version if _live.landscape else "N/A"
    sys_kernel      = _live.landscape.kernel_version if _live.landscape else "N/A"
    sys_hana        = (_live.landscape.hana_version if _live.landscape else None) or "Not on HANA"
    sys_client      = _live.sap_system.client
    sys_host        = _live.sap_system.host
    landscape       = {}

    cc = _live.custom_code
    total_obj       = cc.total_objects if cc else 0
    total_loc       = cc.total_lines_of_code if cc else 0
    z_programs      = len(cc.z_programs) if cc else 0
    func_mods       = len(cc.z_function_modules) if cc else 0
    classes         = len(cc.z_classes) if cc else 0
    custom_tables   = len(cc.custom_tables) if cc else 0
    badis           = len(cc.badis) if cc else 0
    user_exits      = len(cc.user_exits) if cc else 0
    enh_spots       = 0
    modules_covered = ["MM"]

    atc = _live.atc_report
    atc_total       = atc.total_findings if atc else 0
    atc_critical    = atc.critical_count if atc else 0
    atc_high        = atc.high_count if atc else 0
    atc_medium      = atc.medium_count if atc else 0
    atc_low         = atc.low_count if atc else 0
    atc_checked     = atc.objects_checked if atc else 0
    atc_categories  = {}

    sr = _live.simplification_report
    simplif_total   = sr.total_impacts if sr else 0
    simplif_removed = len(sr.removed_transactions) if sr else 0
    simplif_fms     = len(sr.deprecated_function_modules) if sr else 0
    simplif_tabs    = len(sr.deprecated_tables) if sr else 0
    simplif_compat  = len(sr.compatibility_views) if sr else 0
    simplif_uj      = len(sr.universal_journal_impacts) if sr else 0
    simplif_bp      = len(sr.business_partner_items) if sr else 0
    simplif_ml      = len(sr.material_ledger_items) if sr else 0

    rs = _live.readiness_score
    readiness_score = rs.overall_score if rs else 0
    risk_level      = rs.risk_level.value if rs else "unknown"
    effort_days     = rs.estimated_effort_days if rs else 0
    critical_areas  = rs.critical_objects[:5] if rs else []

effort_weeks = max(1, effort_days // 5)


# ─────────────────────────────────────────────────────────────────────────────
# Page header
# ─────────────────────────────────────────────────────────────────────────────
hcol1, hcol2 = st.columns([3, 1])
with hcol1:
    st.markdown(f"## 📦 SAP MM Migration Assessment — `{sys_sid}`")
    st.markdown(f"<span style='color:#94a3b8;font-size:0.9rem'>{sys_desc}</span>", unsafe_allow_html=True)
with hcol2:
    st.markdown(f"""
    <div style='text-align:right;padding-top:8px'>
        <div style='color:#94a3b8;font-size:0.75rem'>Risk Level</div>
        {_badge(risk_level)}
        <div style='color:#94a3b8;font-size:0.72rem;margin-top:4px'>{sys_version}</div>
    </div>
    """, unsafe_allow_html=True)
st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# Top KPI row
# ─────────────────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.markdown(_kpi("Readiness Score", f"{readiness_score:.0f}%", f"Risk: {risk_level.upper()}"), unsafe_allow_html=True)
k2.markdown(_kpi("Custom Objects",  f"{total_obj:,}",          f"LOC: {total_loc:,}"),          unsafe_allow_html=True)
k3.markdown(_kpi("ATC Findings",    str(atc_total),            f"{atc_critical} critical"),      unsafe_allow_html=True)
k4.markdown(_kpi("Simplif. Items",  str(simplif_total),        f"ML: {simplif_ml} · BP: {simplif_bp}"), unsafe_allow_html=True)
k5.markdown(_kpi("Est. Effort",     f"{effort_days}d",         f"≈ {effort_weeks} weeks"),       unsafe_allow_html=True)
k6.markdown(_kpi("HANA Ready",      "Yes" if "HANA" in sys_hana and "Not" not in sys_hana else "No",
                                    sys_hana[:30]),             unsafe_allow_html=True)
st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# Critical areas alert strip
# ─────────────────────────────────────────────────────────────────────────────
if critical_areas:
    st.markdown("##### 🚨 MM Critical Areas Requiring Immediate Attention")
    for area in critical_areas:
        st.markdown(f"<div class='alert-critical'>🔴 {area}</div>", unsafe_allow_html=True)
    st.markdown("")


# ─────────────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────────────
tabs = st.tabs([
    "📊 Overview",
    "🔬 ATC Analysis",
    "📋 Simplification",
    "📦 Custom Code",
    "🏭 MM Process Areas",
    "⚠️  Risk & Effort",
    "📘 Runbook",
    "🗺️  Landscape",
    "📥 Downloads",
])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 – Overview (charts)
# ═════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown("### Migration Readiness Overview")

    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=[
            "Migration Readiness Score",
            "ATC Findings by Severity",
            "Custom Code Composition",
            "Simplification Impact Categories",
            "ATC by Category",
            "Effort Breakdown (Days)",
        ],
        specs=[
            [{"type": "indicator"}, {"type": "bar"},       {"type": "pie"}],
            [{"type": "bar"},       {"type": "pie"},        {"type": "bar"}],
        ],
        vertical_spacing=0.18,
        horizontal_spacing=0.10,
    )

    # ── Readiness gauge ───────────────────────────────────────────────────────
    gauge_color = _risk_color(risk_level)
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=readiness_score,
        number={"suffix": "%", "font": {"size": 28, "color": gauge_color}},
        gauge={
            "axis": {"range": [0, 100], "tickfont": {"color": "#94a3b8"}},
            "bar": {"color": gauge_color},
            "bgcolor": "#1c2028",
            "bordercolor": "#2d3748",
            "steps": [
                {"range": [0, 40],  "color": "#3f1b1b"},
                {"range": [40, 65], "color": "#3f3416"},
                {"range": [65, 100],"color": "#1a3f1e"},
            ],
            "threshold": {"line": {"color": gauge_color, "width": 3}, "value": readiness_score},
        },
    ), row=1, col=1)

    # ── ATC severity bar ──────────────────────────────────────────────────────
    fig.add_trace(go.Bar(
        x=["Critical", "High", "Medium", "Low"],
        y=[atc_critical, atc_high, atc_medium, atc_low],
        marker_color=["#dc2626", "#f97316", "#eab308", "#22c55e"],
        text=[atc_critical, atc_high, atc_medium, atc_low],
        textposition="outside",
        textfont={"color": "#e2e8f0"},
        name="ATC Severity",
    ), row=1, col=2)

    # ── Custom code pie ───────────────────────────────────────────────────────
    fig.add_trace(go.Pie(
        labels=["Z Programs", "Func. Modules", "Classes", "Tables", "BADIs", "Exits", "Enhanc."],
        values=[z_programs, func_mods, classes, custom_tables, badis, user_exits, enh_spots],
        hole=0.45,
        marker_colors=["#3b82f6", "#7c3aed", "#059669", "#d97706", "#dc2626", "#0ea5e9", "#6366f1"],
        textfont={"color": "#e2e8f0", "size": 11},
    ), row=1, col=3)

    # ── Simplification bar ────────────────────────────────────────────────────
    fig.add_trace(go.Bar(
        x=["Removed TX", "Depr. FMs", "Depr. Tables", "Compat Views", "Univ. Journal", "Bus. Partner", "Mat. Ledger"],
        y=[simplif_removed, simplif_fms, simplif_tabs, simplif_compat, simplif_uj, simplif_bp, simplif_ml],
        marker_color=["#7c3aed"] * 7,
        marker_line_color=["#6d28d9"] * 7,
        text=[simplif_removed, simplif_fms, simplif_tabs, simplif_compat, simplif_uj, simplif_bp, simplif_ml],
        textposition="outside",
        textfont={"color": "#e2e8f0"},
        name="Simplification",
    ), row=2, col=1)

    # ── ATC category pie ──────────────────────────────────────────────────────
    if atc_categories:
        fig.add_trace(go.Pie(
            labels=list(atc_categories.keys()),
            values=list(atc_categories.values()),
            hole=0.4,
            marker_colors=["#f97316", "#dc2626", "#3b82f6", "#22c55e"],
            textfont={"color": "#e2e8f0", "size": 11},
        ), row=2, col=2)
    else:
        # Derived from ATC counts as fallback
        fig.add_trace(go.Pie(
            labels=["Critical+High", "Medium", "Low"],
            values=[atc_critical + atc_high, atc_medium, atc_low],
            hole=0.4,
            marker_colors=["#dc2626", "#eab308", "#22c55e"],
        ), row=2, col=2)

    # ── Effort bar ────────────────────────────────────────────────────────────
    effort_components = {
        "Custom Code Fix":  max(1, atc_critical * 2 + atc_high * 1),
        "Material Ledger":  max(5, simplif_ml * 10),
        "WM → EWM":         15 if ("WM" in modules_covered) else 0,
        "BP Conversion":    max(3, simplif_bp * 5),
        "Testing & UAT":    max(10, effort_days // 4),
        "Cutover Prep":     5,
    }
    fig.add_trace(go.Bar(
        x=list(effort_components.keys()),
        y=list(effort_components.values()),
        marker_color=["#3b82f6", "#7c3aed", "#f97316", "#dc2626", "#059669", "#0ea5e9"],
        text=[f"{v}d" for v in effort_components.values()],
        textposition="outside",
        textfont={"color": "#e2e8f0"},
        name="Effort (days)",
    ), row=2, col=3)

    fig.update_layout(
        height=650,
        showlegend=False,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#161b22",
        font=dict(color="#e2e8f0", family="Segoe UI, system-ui, sans-serif", size=11),
        margin=dict(l=20, r=20, t=50, b=20),
    )
    fig.update_xaxes(showgrid=False, color="#94a3b8")
    fig.update_yaxes(showgrid=True,  gridcolor="#2d3748", color="#94a3b8")
    st.plotly_chart(fig, use_container_width=True)

    # Modules covered pills
    if modules_covered:
        st.markdown("**Modules in Scope:**  " +
                    " ".join(f"<span class='mm-pill'>{m}</span>" for m in modules_covered),
                    unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 – ATC Analysis
# ═════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown("### ABAP Test Cockpit (ATC) Findings")
    st.caption(f"Objects checked: {atc_checked:,} · Total findings: {atc_total:,}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🔴 Critical", atc_critical, delta=None)
    col2.metric("🟠 High",     atc_high,     delta=None)
    col3.metric("🟡 Medium",   atc_medium,   delta=None)
    col4.metric("🟢 Low",      atc_low,      delta=None)

    st.markdown("---")

    if _live and _live.atc_report and _live.atc_report.findings:
        # Live findings table
        sev_filter = st.multiselect(
            "Filter by Severity",
            ["critical", "high", "medium", "low"],
            default=["critical", "high"],
        )
        cat_filter = st.multiselect(
            "Filter by Category",
            ["OBSOLETE_API", "SECURITY", "PERFORMANCE", "ROBUSTNESS", "SYNTAX"],
            default=["OBSOLETE_API", "SECURITY"],
        )
        filtered = [
            f for f in _live.atc_report.findings
            if f.priority.value in sev_filter and f.category.value.upper() in cat_filter
        ]
        rows = [{
            "Object":    f.object_name,
            "Type":      f.object_type,
            "Severity":  f.priority.value.upper(),
            "Category":  f.category.value,
            "Message":   f.message[:90] + "…" if len(f.message) > 90 else f.message,
            "Line":      f.line_number or "–",
        } for f in filtered]
        st.dataframe(rows, use_container_width=True, height=400)

    else:
        # Sample-mode: render synthesised view
        st.markdown("#### Finding Distribution (Synthesised from Assessment Data)")
        st.markdown("""
        > *Live finding detail requires running a connected assessment.
        The chart below is synthesised from the assessment summary.*
        """)

        # MM-specific known ATC patterns
        mm_findings_detail = [
            {"Category": "OBSOLETE_API",  "Check": "BAPI_GOODSMVT_CREATE signature",      "Severity": "CRITICAL", "Objects": max(1, atc_critical // 3)},
            {"Category": "OBSOLETE_API",  "Check": "BAPI_MATERIAL_SAVEDATA deprecated",   "Severity": "CRITICAL", "Objects": max(1, atc_critical // 4)},
            {"Category": "OBSOLETE_API",  "Check": "REUSE_ALV_GRID_DISPLAY in MM reports","Severity": "HIGH",     "Objects": max(1, atc_high // 3)},
            {"Category": "OBSOLETE_API",  "Check": "RFC_READ_TABLE – use CDS views",       "Severity": "HIGH",     "Objects": max(1, atc_high // 4)},
            {"Category": "SECURITY",      "Check": "Authority check missing (ME/MIGO)",   "Severity": "CRITICAL", "Objects": max(1, atc_critical // 5)},
            {"Category": "SECURITY",      "Check": "Dynamic SQL in MM reports",            "Severity": "HIGH",     "Objects": max(1, atc_high // 5)},
            {"Category": "PERFORMANCE",   "Check": "SELECT inside GR posting loop",        "Severity": "HIGH",     "Objects": max(1, atc_high // 6)},
            {"Category": "PERFORMANCE",   "Check": "Missing index on MSEG reads",          "Severity": "MEDIUM",   "Objects": max(1, atc_medium // 3)},
            {"Category": "ROBUSTNESS",    "Check": "No SUBRC check after BAPI call",       "Severity": "MEDIUM",   "Objects": max(1, atc_medium // 4)},
        ]
        st.dataframe(mm_findings_detail, use_container_width=True)

    st.markdown("---")
    st.markdown("#### MM-Specific ATC Remediation Guide")
    remediation = {
        "BAPI_GOODSMVT_CREATE": "Review parameter changes in S/4HANA – GMCODE field handling changed. Test all GR/GI scenarios.",
        "BAPI_MATERIAL_SAVEDATA": "Replace with OData service API_PRODUCT_SRV. Map all input fields to new API structure.",
        "REUSE_ALV_GRID_DISPLAY": "Migrate to `CL_SALV_TABLE` or build Fiori OData-based List Report.",
        "RFC_READ_TABLE": "Replace with CDS views (e.g., I_PurchaseOrder, I_MaterialDocument) or custom OData services.",
        "Dynamic SQL (MM)": "Validate all WHERE clause inputs using `CL_ABAP_DYN_PRG→CHECK_COLUMN_NAME`.",
        "Missing Authority Check": "Add `AUTHORITY-CHECK OBJECT 'M_BEST_BSA'` before PO operations; `'M_MSEG_BWA'` for goods movements.",
    }
    for obj, fix in remediation.items():
        with st.expander(f"🔧 `{obj}`"):
            st.markdown(fix)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 – Simplification
# ═════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown("### S/4HANA Simplification Database – MM Impact")
    st.caption("Items that require mandatory action before or during migration")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Items",       simplif_total)
    c2.metric("Material Ledger",   simplif_ml,      help="Mandatory ML activation items")
    c3.metric("Business Partner",  simplif_bp,      help="Customer/Vendor → BP conversion items")
    c4.metric("Univ. Journal",     simplif_uj,      help="ACDOCA / FI-CO unification items")

    st.markdown("---")

    # Render from live state if available, else use MM constant list
    if _live and _live.simplification_report:
        sr = _live.simplification_report
        sections_map = {
            "🛒 Removed Transactions (MM)":     sr.removed_transactions,
            "📌 Deprecated Function Modules":   sr.deprecated_function_modules,
            "🗄️  Deprecated Tables":            sr.deprecated_tables,
            "🔗 Compatibility Views":           sr.compatibility_views,
            "📒 Universal Journal Impacts":     sr.universal_journal_impacts,
            "👤 Business Partner Conversion":   sr.business_partner_items,
            "⚖️  Material Ledger Activation":   sr.material_ledger_items,
        }
        for title, items in sections_map.items():
            with st.expander(f"{title} ({len(items)} items)", expanded=(len(items) > 0 and "Material Ledger" in title)):
                for item in items:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(item.impact.value, "⚪")
                    affected_label = "✅ **Affected**" if item.affected_in_system else "➖ Not Detected"
                    st.markdown(f"{icon} **{item.object_name}** — {item.title}  \n{affected_label} · _{item.migration_note or 'No note'}_")

    else:
        # Use embedded MM simplification list
        for area_key in ["Procurement (P2P)", "Inventory Management", "Warehouse Management (WM→EWM)",
                         "Material Master", "Invoice Verification (LIV)", "MRP & Planning"]:
            meta = MM_PROCESS_AREAS[area_key]
            items = [i for i in MM_CRITICAL_SIMPLIFICATIONS if i["area"] in area_key
                     or any(kw in area_key for kw in [i["area"].split()[0]])]
            with st.expander(f"{meta['icon']} {area_key}", expanded=("Material Master" in area_key)):
                st.caption(" · ".join(f"`{t}`" for t in meta["key_tables"]))
                for change in meta["s4_changes"]:
                    st.markdown(f"- {change}")

        st.markdown("---")
        st.markdown("#### Full MM Simplification Checklist")
        for item in MM_CRITICAL_SIMPLIFICATIONS:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(item["impact"], "⚪")
            c1, c2, c3 = st.columns([1, 3, 1])
            c1.markdown(f"{icon} `{item['object']}`")
            c2.markdown(f"<span style='font-size:0.83rem'>{item['note']}</span>", unsafe_allow_html=True)
            c3.markdown(f"<span class='mm-pill'>{item['area']}</span>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 – Custom Code
# ═════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown("### Custom Code Inventory")

    col_a, col_b, col_c, col_d, col_e, col_f = st.columns(6)
    col_a.metric("Z Programs",   z_programs)
    col_b.metric("Func. Modules",func_mods)
    col_c.metric("Classes",      classes)
    col_d.metric("Custom Tables",custom_tables)
    col_e.metric("BADIs",        badis)
    col_f.metric("User Exits",   user_exits)

    st.markdown(f"**Total:** `{total_obj:,}` objects · `{total_loc:,}` lines of code")
    st.markdown("---")

    if _live and _live.custom_code:
        cc = _live.custom_code
        sub = st.tabs(["Z Programs", "Function Modules", "Classes", "Tables", "BADIs", "User Exits"])
        with sub[0]:
            mm_progs = [p for p in cc.z_programs if any(p.package and mod in p.package.upper()
                        for mod in ["ZMM", "ZMAT", "ZINV", "ZPO", "ZGR"]) or
                        any(pfx in p.object_name.upper() for pfx in ["ZMM_", "ZPO_", "ZGR_", "ZMAT_", "ZINV_"])]
            all_progs = [p.model_dump() for p in cc.z_programs]
            if mm_progs:
                st.info(f"🔍 {len(mm_progs)} MM-prefix programs identified")
                st.dataframe([p.model_dump() for p in mm_progs], use_container_width=True)
            else:
                st.dataframe(all_progs, use_container_width=True)
        with sub[1]:
            st.dataframe([f.model_dump() for f in cc.z_function_modules], use_container_width=True)
        with sub[2]:
            st.dataframe([c.model_dump() for c in cc.z_classes], use_container_width=True)
        with sub[3]:
            mm_tables = [t for t in cc.custom_tables
                         if any(kw in t.object_name.upper() for kw in ["MAT", "VEND", "PURCH", "INV", "PRICE", "MM", "PO", "GR"])]
            st.info(f"🔍 Detected {len(mm_tables)} MM-related custom tables")
            st.dataframe([t.model_dump() for t in cc.custom_tables], use_container_width=True)
        with sub[4]:
            st.dataframe([b.model_dump() for b in cc.badis], use_container_width=True)
        with sub[5]:
            st.dataframe([u.model_dump() for u in cc.user_exits], use_container_width=True)

    else:
        # Sample-mode object breakdown chart
        fig_cc = go.Figure(go.Bar(
            x=["Z Programs", "Func. Modules", "Classes", "Tables", "BADIs", "User Exits", "Enh. Spots"],
            y=[z_programs, func_mods, classes, custom_tables, badis, user_exits, enh_spots],
            marker_color=["#3b82f6", "#7c3aed", "#059669", "#d97706", "#dc2626", "#0ea5e9", "#6366f1"],
            text=[z_programs, func_mods, classes, custom_tables, badis, user_exits, enh_spots],
            textposition="outside",
            textfont={"color": "#e2e8f0"},
        ))
        fig_cc.update_layout(
            height=300,
            paper_bgcolor="#0e1117",
            plot_bgcolor="#161b22",
            font=dict(color="#e2e8f0"),
            margin=dict(l=10, r=10, t=20, b=10),
            showlegend=False,
        )
        fig_cc.update_yaxes(gridcolor="#2d3748")
        st.plotly_chart(fig_cc, use_container_width=True)

        # MM-specific custom object highlights
        st.markdown("#### Known MM Custom Object Patterns")
        mm_obj_patterns = [
            {"Pattern": "ZMM_PO_*",   "Type": "Z Program",       "Purpose": "Custom PO processing & enhancements",        "Risk": "high"},
            {"Pattern": "ZMM_GR_EXIT","Type": "User Exit",        "Purpose": "Goods receipt posting user exit",            "Risk": "critical"},
            {"Pattern": "ZMM_PO_BADI","Type": "BAdI",             "Purpose": "Purchase order BAdI implementation",         "Risk": "high"},
            {"Pattern": "ZMAT_*",     "Type": "Z Program",        "Purpose": "Material master extension reports",          "Risk": "medium"},
            {"Pattern": "ZPRICE_COND","Type": "Custom Table",     "Purpose": "Custom pricing conditions storage",          "Risk": "medium"},
            {"Pattern": "ZVEND_MASTER","Type":"Custom Table",     "Purpose": "Extended vendor master attributes",          "Risk": "high"},
            {"Pattern": "ZMM_RESERVE","Type": "Custom Table",     "Purpose": "Material reservation extensions",            "Risk": "medium"},
            {"Pattern": "ZPURCH_HIST","Type": "Custom Table",     "Purpose": "Custom purchasing history tracking",         "Risk": "low"},
        ]
        rows_cc = [{
            "Pattern": p["Pattern"],
            "Type":    p["Type"],
            "Purpose": p["Purpose"],
            "Risk":    p["Risk"].upper(),
        } for p in mm_obj_patterns]
        st.dataframe(rows_cc, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 – MM Process Areas
# ═════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.markdown("### SAP MM Process Area Migration Impact")
    st.caption("Drill down by functional area to understand migration scope and critical changes")

    for area_name, meta in MM_PROCESS_AREAS.items():
        with st.expander(f"{meta['icon']} **{area_name}** — {meta['desc']}", expanded=False):
            col_l, col_r = st.columns(2)

            with col_l:
                st.markdown("**Key Standard Tables**")
                for t in meta["key_tables"]:
                    st.markdown(f"- `{t}`")
                st.markdown("**Key Transactions**")
                for tx in meta["key_tx"]:
                    st.markdown(f"- `{tx}`")

            with col_r:
                st.markdown("**S/4HANA Changes & Migration Notes**")
                for change in meta["s4_changes"]:
                    st.markdown(f"⚡ {change}")

            # Area-specific risk indicators
            area_risk_items = [i for i in MM_CRITICAL_SIMPLIFICATIONS
                               if i["area"].lower() in area_name.lower()
                               or area_name.lower().split("(")[0].strip().lower() in i["area"].lower()]
            if area_risk_items:
                st.markdown("**Affected Simplification Items in This Area**")
                for item in area_risk_items:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(item["impact"], "⚪")
                    st.markdown(f"{icon} `{item['object']}` — {item['note']}")

    st.markdown("---")
    st.markdown("### WM → EWM Migration Decision Matrix")
    ewm_matrix = [
        {"Question": "Is Classic WM actively used?",               "If Yes": "Plan EWM migration project",           "If No": "Can skip WM→EWM track"},
        {"Question": "Are there Transfer Order user exits?",        "If Yes": "Redesign in EWM PPF actions",          "If No": "Standard EWM migration applies"},
        {"Question": "Physical inventory custom code exists?",      "If Yes": "Rewrite for EWM inventory process",    "If No": "Standard EWM physical inventory"},
        {"Question": "External WMS interface via RFC?",             "If Yes": "Migrate to EWM ODATA/REST API",        "If No": "No interface migration needed"},
        {"Question": "Lean WM acceptable short-term?",             "If Yes": "Use compatibility Lean WM temporarily", "If No": "Full EWM migration required"},
    ]
    st.dataframe(ewm_matrix, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 6 – Risk & Effort
# ═════════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.markdown("### MM Migration Risk & Effort Analysis")

    # Risk gauge + effort donut side by side
    fig_re = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "indicator"}, {"type": "pie"}]],
        subplot_titles=["Migration Readiness", "Effort Distribution"],
    )
    fig_re.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=readiness_score,
        delta={"reference": 65, "decreasing": {"color": "#dc2626"}, "increasing": {"color": "#22c55e"}},
        number={"suffix": "%", "font": {"color": _risk_color(risk_level)}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": _risk_color(risk_level)},
            "bgcolor": "#1c2028",
            "bordercolor": "#2d3748",
            "steps": [
                {"range": [0, 40],  "color": "#3f1b1b"},
                {"range": [40, 65], "color": "#3f3416"},
                {"range": [65, 100],"color": "#1a3f1e"},
            ],
        },
    ), row=1, col=1)
    fig_re.add_trace(go.Pie(
        labels=list(effort_components.keys()),
        values=list(effort_components.values()),
        hole=0.5,
        marker_colors=["#3b82f6", "#7c3aed", "#f97316", "#dc2626", "#059669", "#0ea5e9"],
        textfont={"color": "#e2e8f0"},
    ), row=1, col=2)
    fig_re.update_layout(
        height=380,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#161b22",
        font=dict(color="#e2e8f0"),
        margin=dict(l=10, r=10, t=40, b=10),
        showlegend=True,
        legend=dict(font=dict(color="#94a3b8"), bgcolor="#0e1117"),
    )
    st.plotly_chart(fig_re, use_container_width=True)

    st.markdown("---")

    # Effort table
    st.markdown("#### Estimated Effort by Work Stream")
    effort_table = [
        {"Work Stream": "Custom ABAP Code Remediation",  "Est. Days": max(1, atc_critical * 2 + atc_high),         "Team": "ABAP Development",          "Priority": "CRITICAL"},
        {"Work Stream": "Material Ledger Activation",    "Est. Days": max(5, simplif_ml * 10),                     "Team": "Finance / Controlling",     "Priority": "HIGH"},
        {"Work Stream": "WM → EWM Migration",            "Est. Days": 15 if "WM" in modules_covered else 0,        "Team": "WM / EWM Consultant",       "Priority": "HIGH"},
        {"Work Stream": "Business Partner Conversion",   "Est. Days": max(3, simplif_bp * 5),                      "Team": "MM / FI Functional",        "Priority": "HIGH"},
        {"Work Stream": "Material Master API Migration", "Est. Days": max(3, (simplif_fms // 2) + 3),              "Team": "ABAP + MM Functional",      "Priority": "MEDIUM"},
        {"Work Stream": "Integration Testing (P2P)",     "Est. Days": max(10, effort_days // 4),                   "Team": "QA + Integration Team",     "Priority": "MEDIUM"},
        {"Work Stream": "Cutover Planning & Rehearsal",  "Est. Days": 5,                                           "Team": "PMO + BASIS",               "Priority": "MEDIUM"},
        {"Work Stream": "Hypercare & Stabilisation",     "Est. Days": 10,                                          "Team": "Full Project Team",         "Priority": "LOW"},
    ]
    total_est = sum(r["Est. Days"] for r in effort_table)
    st.dataframe(effort_table, use_container_width=True)
    st.markdown(f"**Total Estimated Effort: `{total_est}` days  ≈  `{max(1, total_est // 5)}` working weeks**")

    st.markdown("---")

    # Risk matrix
    st.markdown("#### MM Risk Matrix")
    risk_matrix = [
        {"Risk Area": "BAPI_GOODSMVT_CREATE API changes",        "Probability": "High",   "Impact": "Critical", "Mitigation": "Unit test all GR/GI BAPI callers in S/4HANA sandbox"},
        {"Risk Area": "Classic WM deprecation",                  "Probability": "High",   "Impact": "Critical", "Mitigation": "Start EWM migration workstream early; use Lean WM as interim"},
        {"Risk Area": "Material Ledger activation side effects",  "Probability": "Medium", "Impact": "High",     "Mitigation": "Activate ML in sandbox first; validate stock valuation reconciliation"},
        {"Risk Area": "Custom MRP logic incompatibility",        "Probability": "Medium", "Impact": "High",     "Mitigation": "Test MRP Live with custom user exits; re-implement in BAdI"},
        {"Risk Area": "Vendor → Business Partner data quality",  "Probability": "Medium", "Impact": "High",     "Mitigation": "Run FLBP data quality checks 3 months before cutover"},
        {"Risk Area": "Custom Price Condition table access",     "Probability": "Low",    "Impact": "Medium",   "Mitigation": "Review EKKO/EKPO reads in pricing routines against CDS views"},
        {"Risk Area": "Inventory reporting via MB51/MB52",       "Probability": "Low",    "Impact": "Medium",   "Mitigation": "Replace with Manage Inventory Fiori app or custom CDS report"},
    ]
    st.dataframe(risk_matrix, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 7 – Runbook
# ═════════════════════════════════════════════════════════════════════════════
with tabs[6]:
    st.markdown("### SAP MM Migration Runbook")

    if _live and _live.runbook:
        rb = _live.runbook
        st.success(f"**{rb.project_name}** — {len(rb.sections)} sections · {rb.total_estimated_duration_weeks} weeks")
        for section in sorted(rb.sections, key=lambda s: s.order):
            with st.expander(f"📌 {section.title}"):
                if section.estimated_duration:
                    st.caption(f"⏱ Duration: {section.estimated_duration}  |  👥 Team: {section.responsible_team or 'TBD'}")
                st.markdown(section.content)
                if section.tasks:
                    st.markdown("**Tasks:**")
                    for task in section.tasks:
                        st.markdown(f"- ☐ {task}")
    else:
        # Embedded MM-specific runbook phases
        mm_runbook = [
            {
                "phase": "Phase 1: Project Setup & Readiness Check",
                "duration": "3 weeks",
                "team": "PMO + SAP MM Consultants",
                "tasks": [
                    "Define MM migration scope (procurement, inventory, WM, MRP)",
                    "Run SAP Readiness Check 2.0 tool",
                    "Download MM-specific Simplification List items",
                    "Install S/4HANA Migration Cockpit",
                    "Set up MM sandbox conversion environment",
                ],
            },
            {
                "phase": "Phase 2: Custom Code Remediation (MM)",
                "duration": "6–10 weeks",
                "team": "ABAP Development Team",
                "tasks": [
                    "Fix all BAPI_GOODSMVT_CREATE callers for S/4HANA API changes",
                    "Migrate BAPI_MATERIAL_SAVEDATA to API_PRODUCT_SRV OData",
                    "Replace BAPI_PO_CREATE1 with MM_PO_* API or keep with testing",
                    "Migrate REUSE_ALV_* in MM reports to CL_SALV_TABLE",
                    "Fix Dynamic SQL in all MM programs",
                    "Add missing authority checks (M_BEST_BSA, M_MSEG_BWA)",
                    "Adapt user exits ZMM_GR_EXIT, ZMM_PO_BADI for S/4HANA",
                    "Re-run ATC and resolve all remaining Critical/High",
                ],
            },
            {
                "phase": "Phase 3: Material Ledger Activation",
                "duration": "3–4 weeks",
                "team": "Finance / Controlling Team",
                "tasks": [
                    "Identify all plants requiring ML activation",
                    "Review current price control (S/V) per material type",
                    "Execute ML activation in sandbox – validate MBEW reconciliation",
                    "Test material price change (MR21) in S/4HANA",
                    "Document impact on CO-PA and actual costing",
                    "Confirm CKMLCR and CKMVFM data migration",
                ],
            },
            {
                "phase": "Phase 4: WM → EWM Migration (if applicable)",
                "duration": "4–8 weeks",
                "team": "WM / EWM Consultant + ABAP",
                "tasks": [
                    "Evaluate: Full EWM vs Lean WM vs Embedded EWM",
                    "Map all Transfer Order types to EWM Warehouse Tasks",
                    "Redesign Transfer Order user exits as EWM PPF actions",
                    "Migrate physical inventory process to EWM",
                    "Test storage bin and quant management",
                    "Validate external WMS interfaces (if any)",
                ],
            },
            {
                "phase": "Phase 5: Business Partner – Vendor Conversion",
                "duration": "2–3 weeks",
                "team": "MM Functional Team",
                "tasks": [
                    "Run LFA1/LFAS data quality checks",
                    "Execute pre-BP migration validation reports",
                    "Run transaction FLBP for vendor BP assignment",
                    "Assign BP role FLVN00 to all vendor master records",
                    "Validate purchasing org data (LFM1) in BP",
                    "Document and correct all exceptions",
                ],
            },
            {
                "phase": "Phase 6: Integration & P2P Cycle Testing",
                "duration": "4 weeks",
                "team": "Integration Team + MM QA",
                "tasks": [
                    "End-to-end P2P: PR → RFQ → PO → GR → Invoice → Payment",
                    "Test all RFC destinations (SRM, APO, external WMS)",
                    "Validate IDoc processing for inbound deliveries",
                    "Test MRP run (MD01 / MRP Live) with migrated data",
                    "Regression test all custom MM reports",
                    "Validate consignment and subcontracting scenarios",
                ],
            },
            {
                "phase": "Phase 7: Cutover & Go-Live",
                "duration": "2 weeks",
                "team": "All Teams + PMO",
                "tasks": [
                    "Freeze MM source system (close open POs, GRs, invoices)",
                    "Execute at least 2 mock cutover rehearsals",
                    "Run SUM (Software Update Manager) conversion",
                    "Execute MM-specific post-conversion checks",
                    "Validate open Purchase Order carry-over",
                    "Release system to business users",
                    "Establish MM hypercare team (10 business days)",
                ],
            },
        ]
        for section in mm_runbook:
            with st.expander(f"📌 {section['phase']}", expanded=False):
                st.caption(f"⏱ Duration: {section['duration']}  |  👥 Team: {section['team']}")
                st.markdown("**Tasks:**")
                for task in section["tasks"]:
                    st.markdown(f"- ☐ {task}")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 8 – Landscape
# ═════════════════════════════════════════════════════════════════════════════
with tabs[7]:
    st.markdown("### System Landscape")

    col_sys, col_land = st.columns(2)
    with col_sys:
        st.markdown("#### System Details")
        st.table({
            "System ID":      sys_sid,
            "Host":           sys_host,
            "Client":         sys_client,
            "SAP Version":    sys_version,
            "Kernel":         sys_kernel,
            "HANA":           sys_hana,
        }.items())

    with col_land:
        st.markdown("#### Landscape Metrics")
        if landscape:
            st.table({
                "App Servers":          landscape.get("app_servers", "N/A"),
                "Active Clients":       landscape.get("active_clients", "N/A"),
                "RFC Destinations":     landscape.get("rfc_destinations", "N/A"),
                "Transport Routes":     landscape.get("transport_routes", "N/A"),
                "Installed Components": landscape.get("installed_components", "N/A"),
            }.items())
        elif _live and _live.landscape:
            lnd = _live.landscape
            st.table({
                "System ID":    lnd.system_id,
                "Hostname":     lnd.hostname,
                "SAP Version":  lnd.sap_version,
                "Kernel":       lnd.kernel_version,
                "HANA":         lnd.hana_version or "N/A",
            }.items())
            if lnd.installed_components:
                st.markdown("#### Installed Components")
                st.dataframe(lnd.installed_components, use_container_width=True)
        else:
            st.info("Landscape details not available for this system.")

    if _live and _live.landscape:
        lnd = _live.landscape
        col_a, col_b = st.columns(2)
        with col_a:
            if lnd.active_clients:
                st.markdown("#### Active Clients")
                st.dataframe([{"Client": c.get("client", ""), "Description": c.get("description", "")}
                               for c in lnd.active_clients], use_container_width=True)
        with col_b:
            if lnd.rfc_destinations:
                st.markdown("#### RFC Destinations")
                st.dataframe(lnd.rfc_destinations, use_container_width=True)

    if modules_covered:
        st.markdown("#### Modules in Scope")
        st.markdown(" ".join(f"<span class='mm-pill'>{m}</span>" for m in modules_covered),
                    unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 9 – Downloads
# ═════════════════════════════════════════════════════════════════════════════
with tabs[8]:
    st.markdown("### Download Reports")

    if _live:
        output_dir = Path("output/reports")
        aid_short = (_live.assessment_id or "")[:8]

        # ── LLM Recommendations ───────────────────────────────────────────
        st.markdown("#### 🤖 LLM Recommendations (IBM Consulting Advantage)")
        rr = _live.recommendation_report
        if rr and rr.recommendations:
            rec_count = len(rr.recommendations)
            critical_count = sum(1 for r in rr.recommendations if r.priority.value == "critical")
            st.success(
                f"**{rec_count} recommendations** generated · "
                f"{critical_count} critical · "
                f"Total effort: {rr.total_effort_days} days · "
                f"Generated: {rr.generated_at.strftime('%Y-%m-%d %H:%M UTC')}"
            )
            col_rec1, col_rec2 = st.columns(2)
            with col_rec1:
                if rr.excel_path and Path(rr.excel_path).exists():
                    with open(rr.excel_path, "rb") as f:
                        st.download_button(
                            "⬇️ Download Recommendations (.xlsx)",
                            f,
                            file_name=Path(rr.excel_path).name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            type="primary",
                        )
                    st.caption(f"📂 `{rr.excel_path}`")
                else:
                    st.warning("Excel file not found — re-run assessment to regenerate")
            with col_rec2:
                if rr.csv_path and Path(rr.csv_path).exists():
                    with open(rr.csv_path, "rb") as f:
                        st.download_button(
                            "⬇️ Download Recommendations (.csv)",
                            f,
                            file_name=Path(rr.csv_path).name,
                            mime="text/csv",
                            use_container_width=True,
                        )
                    st.caption(f"📂 `{rr.csv_path}`")
                else:
                    st.warning("CSV file not found — re-run assessment to regenerate")

            # Quick inline preview
            with st.expander("👁️ Preview recommendations (top 10)"):
                preview = [{
                    "Priority":    r.priority.value.upper(),
                    "Object":      r.object_name,
                    "Problem":     r.problem[:80] + "…" if len(r.problem) > 80 else r.problem,
                    "Fix":         r.recommended_fix[:80] + "…" if len(r.recommended_fix) > 80 else r.recommended_fix,
                    "Effort":      r.estimated_effort,
                    "Days":        r.estimated_duration_days,
                    "Consultant":  r.required_consultant,
                } for r in rr.recommendations[:10]]
                st.dataframe(preview, use_container_width=True)
        else:
            st.info("No LLM recommendations available. Run a live assessment.")

        st.markdown("---")

        # ── Runbook downloads ─────────────────────────────────────────────
        st.markdown("#### 📘 Migration Runbook")
        col_dl1, col_dl2, col_dl3 = st.columns(3)

        with col_dl1:
            st.markdown("##### 📄 PDF")
            if _live.runbook and _live.runbook.pdf_path:
                p = Path(_live.runbook.pdf_path)
                if p.exists():
                    with open(p, "rb") as f:
                        st.download_button("⬇️ Download PDF", f, file_name=p.name,
                                           mime="application/pdf", use_container_width=True)
                else:
                    st.info("PDF not yet generated")
            else:
                st.info("Run assessment to generate")

        with col_dl2:
            st.markdown("##### 📝 DOCX")
            if _live.runbook and _live.runbook.docx_path:
                p = Path(_live.runbook.docx_path)
                if p.exists():
                    with open(p, "rb") as f:
                        st.download_button("⬇️ Download DOCX", f, file_name=p.name,
                                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                           use_container_width=True)
                else:
                    st.info("DOCX not yet generated")
            else:
                st.info("Run assessment to generate")

        with col_dl3:
            st.markdown("##### 📋 Markdown")
            if _live.runbook and _live.runbook.markdown_path:
                p = Path(_live.runbook.markdown_path)
                if p.exists():
                    with open(p, "rb") as f:
                        st.download_button("⬇️ Download Markdown", f, file_name=p.name,
                                           mime="text/markdown", use_container_width=True)
                else:
                    st.info("Markdown not yet generated")
            else:
                st.info("Run assessment to generate")

        dash_path = output_dir / f"dashboard_{aid_short}.html"
        if dash_path.exists():
            st.markdown("---")
            st.markdown("#### 📊 Interactive HTML Dashboard")
            with open(dash_path, "rb") as f:
                st.download_button("⬇️ Download Dashboard HTML", f,
                                   file_name=dash_path.name, mime="text/html",
                                   use_container_width=True)

        # Execution log
        st.markdown("---")
        st.markdown("#### 📋 Assessment Execution Log")
        log_lines = [
            f"Assessment ID  : {_live.assessment_id}",
            f"System         : {_live.sap_system.sid} / {_live.sap_system.host}",
            f"Status         : {_live.status.value}",
            f"Steps Completed: {', '.join(_live.steps_completed)}",
            f"Current Step   : {_live.current_step}",
            f"LLM Backend    : {_live.recommendation_report.generated_at.strftime('%Y-%m-%d %H:%M UTC') if _live.recommendation_report else 'N/A'}",
        ]
        if _live.error_messages:
            log_lines.append("")
            log_lines.append("ERRORS:")
            log_lines.extend(_live.error_messages)
        st.code("\n".join(log_lines), language="text")

    else:
        st.info("Run a live assessment to enable report downloads.")
        st.markdown("""
        Reports available after live assessment:
        - **PDF Runbook** — Full MM migration runbook in A4 PDF
        - **DOCX Runbook** — Word document version
        - **Markdown Runbook** — Plain text version for version control
        - **Interactive HTML Dashboard** — Standalone Plotly charts
        """)


# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<center><small style='color:#4b5563'>Made with IBM Bob · SAP MM Migration Assessment Agent v2.0 · "
    "Module Focus: Materials Management (MM)</small></center>",
    unsafe_allow_html=True,
)
