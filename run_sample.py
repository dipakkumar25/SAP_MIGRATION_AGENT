"""
Run the 9-agent SAP migration assessment pipeline with sample data.
Stubs ONLY the two problem modules (database + orm_models) and FastAPI.

After the pipeline completes, a self-contained HTML dashboard is written to:
    output/reports/dashboard_<assessment_id>_static.html
"""
import sys, json, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

# ── 1. Stub app.models.database BEFORE anything is imported ──────────────────
# This prevents asyncpg / Postgres from being required at import time.
_db = types.ModuleType("app.models.database")
class Base: pass
_db.Base = Base
_db.engine = None
_db.async_session_factory = None
_db.get_db = None
_db.create_all_tables = None
sys.modules["app.models.database"] = _db

# ── 2. Stub app.models.orm_models ────────────────────────────────────────────
_orm = types.ModuleType("app.models.orm_models")
for _n in ("Assessment","ATCRecord","CustomCodeRecord","LandscapeRecord","RiskRecord","ReportFile"):
    setattr(_orm, _n, type(_n, (), {}))
sys.modules["app.models.orm_models"] = _orm

# ── 3. Stub FastAPI-related modules so app/__init__.py can load ───────────────
# We provide a minimal create_app stub.
_api_app = types.ModuleType("app.api.app")
def create_app(): pass
_api_app.create_app = create_app
sys.modules["app.api.app"] = _api_app

for _m in ("fastapi", "starlette", "starlette.status", "starlette.middleware",
           "starlette.middleware.cors", "passlib", "passlib.context",
           "jose", "jose.exceptions", "python_multipart"):
    sys.modules.setdefault(_m, types.ModuleType(_m))

# ── 4. Now import normally — Python resolves real files for everything else ───
from app.graph.workflow import run_assessment
from app.models.schemas import SAPSystem

# ── Multi-system sample configuration ────────────────────────────────────────
# Each entry: (sample_json_file, index_into_array_or_None, assessment_id)
# index=None means the file is a single object (not an array)
_SYSTEMS = [
    ("sample_data/sample_assessment.json",       None, "demo-ECC"),
    ("sample_data/sample_mm_assessments.json",   0,    "demo-MM1"),
    ("sample_data/sample_hr_assessments.json",   0,    "demo-HR1"),
    ("sample_data/sample_sd_assessments.json",   0,    "demo-SD1"),
    ("sample_data/sample_grc_assessments.json",  0,    "demo-GRC1"),
    ("sample_data/sample_apo_assessments.json",  0,    "demo-APO1"),
    ("sample_data/sample_crm_assessments.json",  0,    "demo-CRM1"),
]

print("=" * 60)
print(" SAP Migration Assessment Agent  --  Multi-System Run")
print("=" * 60)
print("Mode   : Mock RFC  |  Rule-based AI (no OpenAI key required)")
print(f"Systems: {len(_SYSTEMS)} SAP systems will be assessed")
print()

all_states = []
for _sample_file, _idx, _aid in _SYSTEMS:
    _raw = json.load(open(_sample_file, encoding="utf-8-sig"))
    _entry = _raw[_idx] if isinstance(_raw, list) else _raw
    _sap   = _entry["sap_system"]
    _desc  = _sap.get("description", "")
    _system = SAPSystem(
        sid=_sap["sid"], host=_sap["host"],
        client=_sap.get("client", "100"),
        description=_desc,
    )
    print(f"  [{_aid}]  Running assessment for {_system.sid} — {_desc[:60]}")
    _state = run_assessment(_system, assessment_id=_aid)
    all_states.append(_state)
    _score = _state.readiness_score.overall_score if _state.readiness_score else 'N/A'
    _risk  = _state.readiness_score.risk_level.value.upper() if _state.readiness_score else 'N/A'
    print(f"           Done  score={_score}  risk={_risk}")

print()

# Use the first state for the single-system dashboard (backward compat)
state = all_states[0]

# ── Generate single-system static HTML dashboard (backward compat) ────────────
from app.reports.html_dashboard import (
    generate_static_dashboard,
    generate_multi_system_dashboard,
    generate_unified_dashboard,
)
_dash_path = Path("output/reports") / f"dashboard_{state.assessment_id}_static.html"
generate_static_dashboard(state, _dash_path)

# ── Generate multi-system comparison dashboard ────────────────────────────────
_multi_dash_path = Path("output/reports") / "dashboard_multi_system.html"
generate_multi_system_dashboard(all_states, _multi_dash_path)

# ── Generate unified SAP Agentic AI dashboard (all systems + deep-dive) ───────
_unified_dash_path = Path("output/reports") / "dashboard_unified_agentic_ai.html"
generate_unified_dashboard(all_states, _unified_dash_path)

print(f"\n{'='*60}")
print(f" Single-system dashboard  -> {_dash_path}")
print(f" Multi-system dashboard   -> {_multi_dash_path}")
print(f" Unified Agentic AI dash  -> {_unified_dash_path}")
print(f"{'='*60}\n")

SEP = "-" * 60
print()
print(SEP)
print("RESULTS SUMMARY")
print(SEP)
print("Status    :", state.status.value)
print("Completed :", state.steps_completed)
print("Errors    :", state.error_messages or "none")

if state.landscape:
    l = state.landscape
    print()
    print("[Agent 1]  LANDSCAPE DISCOVERY")
    print("  System       :", l.system_id, "@", l.hostname)
    print("  SAP Version  :", l.sap_version)
    print("  HANA Version :", l.hana_version)
    print("  Components   :", len(l.installed_components))
    print("  RFC Dests    :", len(l.rfc_destinations))
    print("  Active Clts  :", len(l.active_clients))

if state.custom_code:
    cc = state.custom_code
    print()
    print("[Agent 2]  CUSTOM CODE INVENTORY")
    print("  Total objects:", cc.total_objects)
    print("  Total LOC    :", cc.total_lines_of_code)
    print("  Z Programs   :", len(cc.z_programs))
    print("  Func Modules :", len(cc.z_function_modules))
    print("  Classes      :", len(cc.z_classes))
    print("  Tables       :", len(cc.custom_tables))
    print("  BADIs        :", len(cc.badis), "  User Exits:", len(cc.user_exits))

if state.atc_report:
    a = state.atc_report
    print()
    print("[Agent 3]  ATC FINDINGS")
    print("  Total        :", a.total_findings)
    print("  Critical:", a.critical_count, "  High:", a.high_count, "  Medium:", a.medium_count, "  Low:", a.low_count)
    if a.findings:
        f = a.findings[0]
        print("  Sample       :", f.object_name, "-", f.check_title, "[" + f.priority.value.upper() + "]")

if state.simplification_report:
    sr = state.simplification_report
    print()
    print("[Agent 4]  SIMPLIFICATION ANALYSIS")
    print("  Total impacts   :", sr.total_impacts)
    print("  Critical items  :", sr.critical_impacts)
    print("  Removed TX      :", len(sr.removed_transactions))
    print("  Deprecated FMs  :", len(sr.deprecated_function_modules))
    print("  Deprecated TBLs :", len(sr.deprecated_tables))
    print("  Business Partner:", len(sr.business_partner_items))
    print("  Universal Jrnl  :", len(sr.universal_journal_impacts))

if state.dependency_graph:
    dg = state.dependency_graph
    print()
    print("[Agent 5]  DEPENDENCY GRAPH")
    print("  Nodes      :", len(dg.nodes))
    print("  Edges      :", len(dg.edges))
    print("  Max depth  :", dg.max_depth)

if state.readiness_score:
    rs = state.readiness_score
    print()
    print("[Agent 6]  RISK ASSESSMENT")
    print("  Score      :", rs.overall_score, "/ 100")
    print("  Risk level :", rs.risk_level.value.upper())
    print("  Effort     :", rs.estimated_effort_days, "days")
    print("  Objects    :", len(rs.object_scores), "scored")
    print("  Critical   :", rs.critical_objects[:5])
    print("  High-risk  :", rs.high_risk_objects[:5])

if state.recommendation_report:
    rr = state.recommendation_report
    print()
    print("[Agent 7]  RECOMMENDATIONS")
    print("  Total recs  :", len(rr.recommendations))
    print("  Total effort:", rr.total_effort_days, "days")
    for r in rr.recommendations[:4]:
        print("  [" + r.priority.value.upper() + "]", r.object_name + ":", r.problem[:75])

if state.runbook:
    rb = state.runbook
    print()
    print("[Agent 8]  MIGRATION RUNBOOK")
    print("  Project  :", rb.project_name)
    print("  Sections :", len(rb.sections))
    print("  Duration :", rb.total_estimated_duration_weeks, "weeks")
    if rb.markdown_path:
        print("  Markdown :", rb.markdown_path)
    if rb.pdf_path:
        print("  PDF      :", rb.pdf_path)
    if rb.docx_path:
        print("  DOCX     :", rb.docx_path)

out_dir = Path("output/reports")
output_files = sorted(out_dir.glob("*")) if out_dir.exists() else []
print()
print("[Agent 9]  DASHBOARD / OUTPUT FILES")
if output_files:
    for f in output_files:
        print("  ", f.name, "(" + str(f.stat().st_size) + " bytes)")
else:
    print("  (plotly not installed -- dashboard skipped)")

# ── Final output links summary ────────────────────────────────────────────────
print()
print("=" * 60)
print(" OUTPUT LINKS")
print("=" * 60)
aid = state.assessment_id[:8]
_reports = Path("output/reports")

_runbook_links = []
if state.runbook:
    if state.runbook.markdown_path:
        _runbook_links.append(("Runbook (Markdown)", state.runbook.markdown_path))
    if state.runbook.pdf_path:
        _runbook_links.append(("Runbook (PDF)     ", state.runbook.pdf_path))
    if state.runbook.docx_path:
        _runbook_links.append(("Runbook (DOCX)    ", state.runbook.docx_path))

_dash_html = _reports / f"dashboard_{aid}_static.html"
_dash_plotly = _reports / f"dashboard_{aid}.html"

for label, link in _runbook_links:
    print(f"  {label} : {link}")

if _dash_html.exists():
    print(f"  Dashboard (Single): {_dash_html}")
elif _dash_plotly.exists():
    print(f"  Dashboard (Single): {_dash_plotly}")
else:
    print("  Dashboard (Single): (not generated — install plotly for interactive dashboard)")

if _multi_dash_path.exists():
    print(f"  Dashboard (Multi) : {_multi_dash_path}")

if _unified_dash_path.exists():
    print(f"  Dashboard (Unified Agentic AI) : {_unified_dash_path}")

print()
print("=" * 60)
print(" All agents ran successfully.")
print("=" * 60)
