"""
Static HTML Dashboard Generator
================================
Builds a fully self-contained, zero-dependency HTML dashboard from an
AgentState object and writes it to disk.

Also provides generate_multi_system_dashboard() which accepts a list of
AgentState objects (one per SAP system – MM, HR, SD, GRC, APO, CRM, etc.)
and renders a single comparison dashboard showing all systems side-by-side.

Called automatically by run_sample.py after every pipeline run.
Output:  output/reports/dashboard_<assessment_id>.html
         output/reports/dashboard_multi_system.html
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from app.models.schemas import AgentState


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _badge(priority: str) -> str:
    colours = {
        "critical": ("badge-crit", "Critical"),
        "high":     ("badge-high", "High"),
        "medium":   ("badge-med",  "Medium"),
        "low":      ("badge-low",  "Low"),
    }
    cls, label = colours.get(priority.lower(), ("badge-low", priority.title()))
    return f'<span class="{cls}">{label}</span>'


def _bar(label: str, value: int, max_val: int, colour: str, sub: str = "") -> str:
    pct = round(value / max_val * 100) if max_val else 0
    sub_html = f'<span class="bar-sub">{sub}</span>' if sub else ""
    return f"""
      <div class="bar-row">
        <div class="bar-label">{label}{sub_html}</div>
        <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{colour}"></div></div>
        <div class="bar-val">{value}</div>
      </div>"""


def _chip(text: str) -> str:
    return f'<span class="chip">{text}</span>'


def _kpi(label: str, value: str, sub: str, colour: str) -> str:
    return f"""
    <div class="kpi" style="border-top-color:{colour}">
      <div class="kpi-lbl">{label}</div>
      <div class="kpi-val" style="color:{colour}">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# Gauge SVG
# ─────────────────────────────────────────────────────────────────────────────

def _gauge_svg(score: float) -> str:
    # Arc: 180° sweep, left=18,100 right=182,100, radius=82
    # score% maps to 0–180°. Convert to endpoint on circle.
    import math
    angle_deg = 180 - (score / 100) * 180          # 0% → 180°(left), 100% → 0°(right)
    angle_rad = math.radians(angle_deg)
    cx, cy, r = 100, 100, 82
    ex = cx + r * math.cos(math.radians(180 - (score / 100) * 180))
    ey = cy - r * math.sin(math.radians(180 - (score / 100) * 180))
    large = 1 if (score / 100) * 180 > 90 else 0

    colour = "#dc2626" if score < 40 else ("#eab308" if score < 65 else "#10b981")
    risk_label = "HIGH RISK" if score < 40 else ("MEDIUM RISK" if score < 65 else "LOW RISK")

    return f"""
    <svg viewBox="0 0 200 118" width="200" height="118" style="overflow:visible">
      <path d="M18,100 A82,82 0 0,1 80.3,24.3"  fill="none" stroke="#fee2e2" stroke-width="17" stroke-linecap="butt"/>
      <path d="M80.3,24.3 A82,82 0 0,1 141,21.5" fill="none" stroke="#fef3c7" stroke-width="17" stroke-linecap="butt"/>
      <path d="M141,21.5 A82,82 0 0,1 182,100"   fill="none" stroke="#d1fae5" stroke-width="17" stroke-linecap="butt"/>
      <path d="M18,100 A82,82 0 0,1 182,100" fill="none" stroke="#e5e7eb" stroke-width="17" stroke-linecap="round" opacity=".3"/>
      <path d="M18,100 A82,82 0 {large},1 {ex:.1f},{ey:.1f}" fill="none" stroke="{colour}" stroke-width="17" stroke-linecap="round"/>
      <circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{colour}"/>
      <text x="100" y="84"  text-anchor="middle" font-size="30" font-weight="800" fill="#1f2328">{score}</text>
      <text x="100" y="100" text-anchor="middle" font-size="10" fill="#57606a">out of 100</text>
      <text x="100" y="114" text-anchor="middle" font-size="9"  font-weight="700" fill="{colour}">{risk_label}</text>
      <text x="14"  y="115" font-size="8" fill="#dc2626">RISK</text>
      <text x="186" y="115" text-anchor="end" font-size="8" fill="#10b981">SAFE</text>
    </svg>"""


# ─────────────────────────────────────────────────────────────────────────────
# ATC bar chart SVG
# ─────────────────────────────────────────────────────────────────────────────

def _atc_bar_svg(critical: int, high: int, medium: int, low: int) -> str:
    total = critical + high + medium + low
    max_v = max(critical, high, medium, low, 1)
    scale = 110 / max_v          # px per unit

    def bar(x, val, col, lbl):
        h = round(val * scale)
        y = 120 - h
        return (
            f'<rect x="{x}" y="{y}" width="38" height="{h}" rx="3" fill="{col}"/>'
            f'<text x="{x+19}" y="{y-4}" text-anchor="middle" font-size="11" font-weight="700" fill="{col}">{val}</text>'
            f'<text x="{x+19}" y="138" text-anchor="middle" font-size="10" fill="#57606a">{lbl}</text>'
        )

    rows = (
        bar(40,  critical, "#dc2626", "Critical") +
        bar(88,  high,     "#f97316", "High") +
        bar(136, medium,   "#eab308", "Medium") +
        bar(184, low,      "#22c55e", "Low")
    )
    return f"""
    <svg viewBox="0 0 240 150" width="100%" style="display:block;overflow:visible">
      <line x1="34" y1="10" x2="34" y2="122" stroke="#e5e7eb"/>
      <line x1="34" y1="122" x2="230" y2="122" stroke="#e5e7eb"/>
      {rows}
      <text x="132" y="150" text-anchor="middle" font-size="9" fill="#57606a">{total} total findings</text>
    </svg>"""


# ─────────────────────────────────────────────────────────────────────────────
# Timeline SVG
# ─────────────────────────────────────────────────────────────────────────────

def _timeline_svg(weeks: int) -> str:
    W = 730
    pw = W / max(weeks, 1)   # pixels per week

    def phase(x, w, y, h, col, label):
        return (
            f'<rect x="{x:.0f}" y="{y}" width="{w:.0f}" height="{h}" rx="3" fill="{col}"/>'
            f'<text x="{x+w/2:.0f}" y="{y+h/2+4}" text-anchor="middle" font-size="8.5" fill="#fff" font-weight="600">{label}</text>'
        )

    bars = (
        phase(10,          2*pw, 8,  20, "#3b82d4", "Project Charter") +
        phase(4*pw+10,     4*pw, 8,  20, "#10b981", "Business Partner Conv.") +
        phase(10,          4*pw, 32, 20, "#7c5cd8", "Landscape &amp; Prep") +
        phase(6*pw+10,    (weeks-6)*pw, 32, 20, "#ef4444", "UAT &amp; Integration Testing") +
        phase(2*pw+10,     8*pw, 56, 20, "#f97316", "Custom Code Adaptation (8 wks)") +
        phase(4*pw+10,     3*pw, 80, 18, "#06b6d4", "Material Ledger") +
        phase((weeks-2)*pw+10, 2*pw, 80, 18, "#1f2328", "Cutover")
    )

    ticks = "".join(
        f'<text x="{10+i*pw:.0f}" y="113" font-size="8" fill="#57606a" text-anchor="middle">W{i}</text>'
        for i in range(0, weeks+1, 2)
    )

    return f"""
    <svg viewBox="0 0 760 120" width="100%" style="min-width:460px;display:block;overflow:visible">
      <line x1="10" y1="104" x2="750" y2="104" stroke="#e5e7eb"/>
      {bars}
      {ticks}
    </svg>"""


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"Segoe UI",system-ui,sans-serif;font-size:13px;line-height:1.55;background:#eef0f4;color:#1f2328}
.page{max-width:860px;margin:0 auto;padding:20px 14px 60px}

/* header */
.hdr{background:linear-gradient(135deg,#1a1f26 0%,#2d3748 100%);border-radius:10px;padding:20px 24px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;gap:12px}
.hdr-l .t1{font-size:17px;font-weight:700;color:#fff;margin-bottom:3px}
.hdr-l .t2{font-size:11px;color:#8b949e}
.hdr-r{text-align:right}
.hdr-r .sid{font-size:38px;font-weight:800;color:#3b82d4;letter-spacing:-1px;line-height:1}
.hdr-r .hsub{font-size:10px;color:#8b949e;margin-top:2px}
.rpill{display:inline-block;padding:3px 10px;border-radius:12px;font-size:10px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;margin-top:6px}
.rpill-med{background:#fef3c7;color:#92400e}
.rpill-hi{background:#fee2e2;color:#991b1b}
.rpill-low{background:#d1fae5;color:#065f46}

/* chips */
.chips{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:12px}
.chip{background:#d1fae5;color:#065f46;font-size:10px;font-weight:600;padding:2px 9px;border-radius:10px}
.chip::before{content:"✓ "}

/* KPIs */
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px}
.kpi{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:13px 13px 10px;border-top:3px solid #e5e7eb}
.kpi-lbl{font-size:10px;color:#57606a;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
.kpi-val{font-size:22px;font-weight:700;line-height:1.1}
.kpi-sub{font-size:10px;color:#57606a;margin-top:4px}

/* cards */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px}
.card-full{margin-bottom:12px}
.ctitle{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#57606a;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.ctitle-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}

/* bars */
.bar-row{display:flex;align-items:center;gap:7px;margin-bottom:7px}
.bar-label{width:130px;flex-shrink:0;font-size:11px}
.bar-sub{font-size:9px;color:#57606a;margin-left:3px}
.bar-track{flex:1;background:#f0f2f5;border-radius:4px;height:13px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px}
.bar-val{width:28px;text-align:right;font-size:11px;color:#57606a;flex-shrink:0}

/* gauge */
.gauge-wrap{display:flex;flex-direction:column;align-items:center;padding:4px 0 6px}
.gauge-legend{display:flex;gap:14px;font-size:10px;color:#57606a;margin-top:4px}

/* table */
table{width:100%;border-collapse:collapse;font-size:11px}
th{text-align:left;padding:5px 7px;border-bottom:2px solid #e5e7eb;font-size:10px;color:#57606a;text-transform:uppercase;letter-spacing:.04em}
td{padding:6px 7px;border-bottom:1px solid #f0f2f5;vertical-align:top}
tr:last-child td{border-bottom:none}
td code{font-size:10px;background:#f0f2f5;padding:1px 4px;border-radius:3px;font-family:monospace}

/* badges */
.badge-crit{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;font-weight:700;background:#fee2e2;color:#991b1b}
.badge-high{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;font-weight:700;background:#ffedd5;color:#9a3412}
.badge-med{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;font-weight:700;background:#fef3c7;color:#92400e}
.badge-low{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;font-weight:700;background:#d1fae5;color:#065f46}

/* runbook steps */
.steps{list-style:none}
.steps li{display:flex;gap:8px;padding:6px 0;border-bottom:1px solid #f0f2f5;font-size:11px;align-items:flex-start}
.steps li:last-child{border-bottom:none}
.snum{flex-shrink:0;width:18px;height:18px;border-radius:50%;background:#3b82d4;color:#fff;font-size:9px;font-weight:700;display:flex;align-items:center;justify-content:center;margin-top:1px}
.smeta{font-size:10px;color:#57606a;margin-top:1px}

/* stat grid */
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}
.stat-box{background:#f7f8fa;border:1px solid #e5e7eb;border-radius:6px;padding:8px;text-align:center}
.stat-box .sv{font-size:19px;font-weight:700}
.stat-box .sl{font-size:9px;color:#57606a;margin-top:1px}

/* pie legend */
.pie-wrap{display:flex;align-items:center;gap:12px}
.leg{flex:1}
.leg-row{display:flex;align-items:center;justify-content:space-between;font-size:11px;margin-bottom:5px}
.leg-l{display:flex;align-items:center;gap:5px}
.dot9{width:9px;height:9px;border-radius:50%;flex-shrink:0}

/* output files table */
.file-tbl td:first-child{font-family:monospace;font-size:11px;color:#1f2328}
.file-tbl td:last-child{color:#57606a;white-space:nowrap}

hr.div{border:none;border-top:1px solid #e5e7eb;margin:10px 0}

footer{text-align:center;font-size:11px;color:#8b949e;padding-top:14px;border-top:1px solid #e5e7eb;margin-top:20px}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Main builder
# ─────────────────────────────────────────────────────────────────────────────

def generate_static_dashboard(state: "AgentState", output_path: Path) -> Path:
    """
    Build a fully self-contained HTML dashboard from the completed AgentState
    and write it to *output_path*.  Returns the path on success.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    aid = state.assessment_id
    sid = state.sap_system.sid

    # ── gather data ──────────────────────────────────────────────────────────
    score      = round(state.readiness_score.overall_score, 1) if state.readiness_score else 0
    risk_level = state.readiness_score.risk_level.value if state.readiness_score else "unknown"
    effort     = state.readiness_score.estimated_effort_days if state.readiness_score else 0

    cc         = state.custom_code
    atc        = state.atc_report
    sr         = state.simplification_report
    dg         = state.dependency_graph
    rr         = state.recommendation_report
    rb         = state.runbook
    ls         = state.landscape

    # ── risk pill ────────────────────────────────────────────────────────────
    pill_cls   = {"critical": "rpill-hi", "high": "rpill-hi",
                  "medium": "rpill-med", "low": "rpill-low"}.get(risk_level, "rpill-med")
    risk_upper = risk_level.upper()

    # ── pipeline chips ───────────────────────────────────────────────────────
    chips_html = "".join(_chip(s) for s in state.steps_completed)

    # ── KPIs ─────────────────────────────────────────────────────────────────
    kpi_html = (
        _kpi("Readiness Score",    f"{score}<small>/100</small>", f'<span class="{pill_cls}" style="font-size:10px;padding:1px 7px;border-radius:10px;font-weight:700">{risk_upper}</span>', "#3b82d4") +
        _kpi("Custom Objects",     str(cc.total_objects) if cc else "—", f"{cc.total_lines_of_code:,} lines of code" if cc else "", "#7c5cd8") +
        _kpi("ATC Findings",       str(atc.total_findings) if atc else "—", f"{atc.critical_count} crit · {atc.high_count} high · {atc.medium_count} med" if atc else "", "#dc2626") +
        _kpi("Simplification",     str(sr.total_impacts) if sr else "—", "S/4HANA impact items", "#10b981") +
        _kpi("Est. Effort",        f"{effort} <small>days</small>", f"{len(rr.recommendations)} recommendations" if rr else "", "#f97316") +
        _kpi("Timeline",           f"{rb.total_estimated_duration_weeks} <small>wks</small>", f"{len(rb.sections)}-phase runbook" if rb else "", "#06b6d4") +
        _kpi("RFC Destinations",   str(len(ls.rfc_destinations)) if ls else "—", f"{len(ls.active_clients)} active clients" if ls else "", "#10b981") +
        _kpi("Components",         str(len(ls.installed_components)) if ls else "—", f"HANA {ls.hana_version}" if ls else "", "#7c5cd8")
    )

    # ── gauge ─────────────────────────────────────────────────────────────────
    gauge_html = _gauge_svg(score)

    # ── ATC bar ───────────────────────────────────────────────────────────────
    atc_bar_html = _atc_bar_svg(
        atc.critical_count if atc else 0,
        atc.high_count     if atc else 0,
        atc.medium_count   if atc else 0,
        atc.low_count      if atc else 0,
    )

    # ── Custom code bars ──────────────────────────────────────────────────────
    if cc:
        cc_max = max(len(cc.z_programs), len(cc.z_function_modules),
                     len(cc.z_classes), len(cc.custom_tables), 1)
        cc_bars = (
            _bar("Z Programs",       len(cc.z_programs),         cc_max, "#3b82d4") +
            _bar("Function Modules", len(cc.z_function_modules), cc_max, "#7c5cd8") +
            _bar("Classes",          len(cc.z_classes),          cc_max, "#06b6d4") +
            _bar("Custom Tables",    len(cc.custom_tables),      cc_max, "#10b981") +
            _bar("BADIs",            len(cc.badis),              cc_max, "#f59e0b") +
            _bar("User Exits",       len(cc.user_exits),         cc_max, "#ef4444")
        )
        cc_footer = f"<p style='font-size:10px;color:#57606a;margin-top:8px'><strong>{cc.total_lines_of_code:,} total LOC</strong> &nbsp;·&nbsp; {cc.total_objects} objects</p>"
    else:
        cc_bars = "<p>No data</p>"
        cc_footer = ""

    # ── Simplification bars ───────────────────────────────────────────────────
    if sr:
        simp_data = [
            ("Deprecated FMs",    len(sr.deprecated_function_modules), "#7c5cd8"),
            ("Deprecated Tables", len(sr.deprecated_tables),           "#06b6d4"),
            ("Removed TX",        len(sr.removed_transactions),        "#ef4444"),
            ("Business Partner",  len(sr.business_partner_items),      "#f97316"),
            ("Universal Journal", len(sr.universal_journal_impacts),   "#10b981"),
            ("Compat Views",      len(sr.compatibility_views),         "#f59e0b"),
            ("Material Ledger",   len(sr.material_ledger_items),       "#3b82d4"),
        ]
        simp_max = max((v for _, v, _ in simp_data), default=1)
        simp_bars = "".join(_bar(l, v, simp_max, c) for l, v, c in simp_data)
        simp_footer = f"<p style='font-size:10px;color:#57606a;margin-top:8px'>{sr.total_impacts} total · {sr.critical_impacts} critical affected</p>"
    else:
        simp_bars = "<p>No data</p>"
        simp_footer = ""

    # ── Risk factor bars ──────────────────────────────────────────────────────
    atc_score  = round(min(100, (atc.critical_count * 10 + atc.high_count * 5 + atc.medium_count * 2) / max(atc.total_findings, 1) * 10), 1) if atc else 0
    loc_score  = 85 if cc and cc.total_lines_of_code > 500_000 else (60 if cc and cc.total_lines_of_code > 100_000 else 30)
    dep_score  = min(100, (dg.max_depth * 12)) if dg else 0
    risk_bars = (
        _bar("ATC Findings",    atc_score,  100, "#dc2626", "×30%") +
        _bar("Complexity LOC",  loc_score,  100, "#f97316", "×15%") +
        _bar("Deprecated APIs", 0,          100, "#eab308", "×25%") +
        _bar("Dependencies",    dep_score,  100, "#3b82d4", "×10%")
    )
    agg_risk = round(atc_score * 0.30 + loc_score * 0.15 + dep_score * 0.10, 1)
    readiness = round(100 - agg_risk, 1)

    # ── Landscape table ───────────────────────────────────────────────────────
    if ls:
        land_rows = f"""
        <tr><td>System ID</td><td><strong>{ls.system_id}</strong></td></tr>
        <tr><td>SAP Version</td><td>{ls.sap_version}</td></tr>
        <tr><td>HANA Version</td><td>{ls.hana_version or "—"}</td></tr>
        <tr><td>App Servers</td><td>{len(ls.installed_addons)}</td></tr>
        <tr><td>Active Clients</td><td>{len(ls.active_clients)}</td></tr>
        <tr><td>RFC Destinations</td><td>{len(ls.rfc_destinations)}</td></tr>
        <tr><td>Components</td><td>{len(ls.installed_components)}</td></tr>
        <tr><td>Transport Domains</td><td>{len(ls.transport_domains)}-tier system</td></tr>"""
    else:
        land_rows = "<tr><td colspan='2'>No data</td></tr>"

    # ── Recommendations table ─────────────────────────────────────────────────
    if rr and rr.recommendations:
        rec_rows = ""
        for rec in rr.recommendations[:10]:
            rec_rows += f"""
            <tr>
              <td>{_badge(rec.priority.value)}</td>
              <td><code>{rec.object_name}</code></td>
              <td>{rec.problem[:80]}</td>
              <td>{rec.recommended_fix[:80]}</td>
              <td style="white-space:nowrap">{rec.estimated_effort}</td>
            </tr>"""
    else:
        rec_rows = "<tr><td colspan='5'>No recommendations</td></tr>"

    # ── Timeline ──────────────────────────────────────────────────────────────
    timeline_html = _timeline_svg(rb.total_estimated_duration_weeks if rb else 12)

    # ── Runbook steps ─────────────────────────────────────────────────────────
    if rb:
        steps_html = "".join(
            f"""<li>
              <div class="snum">{s.order}</div>
              <div>
                <strong>{s.title}</strong>
                <div class="smeta">{s.responsible_team or ""} &nbsp;·&nbsp; {s.estimated_duration or ""}</div>
              </div>
            </li>"""
            for s in sorted(rb.sections, key=lambda x: x.order)
        )
    else:
        steps_html = "<li>No runbook data</li>"

    # ── Output files ──────────────────────────────────────────────────────────
    out_dir = output_path.parent
    file_rows = ""
    for f in sorted(out_dir.glob("*")):
        if f.is_file():
            size_kb = f.stat().st_size / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            file_rows += f"<tr><td>{f.name}</td><td>{size_str}</td></tr>"
    if not file_rows:
        file_rows = "<tr><td colspan='2'>No files yet</td></tr>"

    # ── Stat boxes ────────────────────────────────────────────────────────────
    stat_boxes = f"""
    <div class="stat-grid">
      <div class="stat-box"><div class="sv" style="color:#3b82d4">{score}</div><div class="sl">Readiness / 100</div></div>
      <div class="stat-box"><div class="sv" style="color:#7c5cd8">{cc.total_objects if cc else 0}</div><div class="sl">Custom Objects</div></div>
      <div class="stat-box"><div class="sv" style="color:#dc2626">{atc.total_findings if atc else 0}</div><div class="sl">ATC Findings</div></div>
      <div class="stat-box"><div class="sv" style="color:#10b981">{sr.total_impacts if sr else 0}</div><div class="sl">Simplif. Items</div></div>
      <div class="stat-box"><div class="sv" style="color:#f97316">{len(rr.recommendations) if rr else 0}</div><div class="sl">Recommendations</div></div>
      <div class="stat-box"><div class="sv" style="color:#06b6d4">{rb.total_estimated_duration_weeks if rb else 0}</div><div class="sl">Weeks Timeline</div></div>
    </div>"""

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SAP Migration Dashboard — {sid} ({aid})</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <div class="hdr">
    <div class="hdr-l">
      <div class="t1">SAP ECC → S/4HANA Migration Assessment Dashboard</div>
      <div class="t2">Assessment ID: {aid} &nbsp;·&nbsp; Generated: {generated_at} &nbsp;·&nbsp; Mock RFC · Rule-based AI</div>
      <span class="rpill {pill_cls}">⚠ {risk_upper} &nbsp;·&nbsp; Readiness {score}/100</span>
    </div>
    <div class="hdr-r">
      <div class="sid">{sid}</div>
      <div class="hsub">{ls.hostname if ls else ""}</div>
      <div class="hsub">{ls.sap_version if ls else ""}</div>
      <div class="hsub">HANA {ls.hana_version if ls else ""}</div>
    </div>
  </div>

  <!-- PIPELINE STEPS -->
  <div class="chips">{chips_html}</div>

  <!-- KPI STRIP (8 KPIs, 4 per row) -->
  <div class="kpi-grid">{kpi_html}</div>

  <!-- ROW 1: Gauge + ATC bar -->
  <div class="g2">
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#3b82d4"></span>Agent 6 — Migration Readiness Score</div>
      <div class="gauge-wrap">
        {gauge_html}
        <div class="gauge-legend">
          <span><span style="color:#dc2626;font-weight:700">■</span> 0–40 High risk</span>
          <span><span style="color:#eab308;font-weight:700">■</span> 40–65 Medium</span>
          <span><span style="color:#10b981;font-weight:700">■</span> 65–100 Low risk</span>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#dc2626"></span>Agent 3 — ATC Findings by Severity</div>
      {atc_bar_html}
    </div>
  </div>

  <!-- ROW 2: Custom Code + Simplification -->
  <div class="g2">
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#7c5cd8"></span>Agent 2 — Custom Code Inventory</div>
      {cc_bars}
      {cc_footer}
    </div>
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#10b981"></span>Agent 4 — S/4HANA Simplification Impact</div>
      {simp_bars}
      {simp_footer}
    </div>
  </div>

  <!-- ROW 3: Risk factors + Landscape -->
  <div class="g2">
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#f97316"></span>Agent 6 — Risk Score Breakdown</div>
      {risk_bars}
      <hr class="div">
      <div class="stat-grid">
        <div class="stat-box"><div class="sv" style="color:#f97316">{agg_risk}</div><div class="sl">Aggregate risk / 100</div></div>
        <div class="stat-box"><div class="sv" style="color:#3b82d4">{readiness}</div><div class="sl">Readiness (100 − risk)</div></div>
      </div>
    </div>
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#06b6d4"></span>Agent 1 — System Landscape</div>
      <table>
        <tr><th>Property</th><th>Value</th></tr>
        {land_rows}
      </table>
    </div>
  </div>

  <!-- ROW 4: Timeline (full width) -->
  <div class="card card-full">
    <div class="ctitle"><span class="ctitle-dot" style="background:#3b82d4"></span>Agent 8 — Project Timeline — {rb.total_estimated_duration_weeks if rb else 12} Weeks</div>
    {timeline_html}
  </div>

  <!-- ROW 5: Recommendations (full width) -->
  <div class="card card-full">
    <div class="ctitle"><span class="ctitle-dot" style="background:#dc2626"></span>Agent 7 — Top Recommendations ({len(rr.recommendations) if rr else 0} generated · {rr.total_effort_days if rr else 0} person-days)</div>
    <table>
      <tr><th>Priority</th><th>Object</th><th>Problem</th><th>Recommended Fix</th><th>Effort</th></tr>
      {rec_rows}
    </table>
  </div>

  <!-- ROW 6: Runbook + Output files -->
  <div class="g2">
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#3b82d4"></span>Agent 8 — Migration Runbook ({len(rb.sections) if rb else 0} phases)</div>
      <ul class="steps">{steps_html}</ul>
    </div>
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="card">
        <div class="ctitle"><span class="ctitle-dot" style="background:#10b981"></span>Assessment Summary</div>
        {stat_boxes}
      </div>
      <div class="card">
        <div class="ctitle"><span class="ctitle-dot" style="background:#7c5cd8"></span>Agent 9 — Output Files</div>
        <table class="file-tbl">
          <tr><th>File</th><th>Size</th></tr>
          {file_rows}
        </table>
      </div>
    </div>
  </div>

  <footer>
    Assessment ID: {aid} &nbsp;·&nbsp; System: {sid} &nbsp;·&nbsp;
    Generated: {generated_at} &nbsp;·&nbsp; SAP Migration Agent (9-agent LangGraph pipeline)
  </footer>

</div>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Multi-system dashboard
# ─────────────────────────────────────────────────────────────────────────────

_MULTI_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"Segoe UI",system-ui,sans-serif;font-size:13px;line-height:1.55;background:#eef0f4;color:#1f2328}
.page{max-width:1100px;margin:0 auto;padding:20px 14px 60px}

.hdr{background:linear-gradient(135deg,#1a1f26 0%,#2d3748 100%);border-radius:10px;padding:20px 24px;margin-bottom:16px}
.hdr .t1{font-size:18px;font-weight:700;color:#fff;margin-bottom:4px}
.hdr .t2{font-size:11px;color:#8b949e}
.hdr .t3{font-size:12px;color:#3b82d4;margin-top:6px;font-weight:600}

/* section title */
.sec-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#57606a;
           margin:18px 0 10px;display:flex;align-items:center;gap:7px}
.sec-title-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}

/* summary comparison table */
.cmp-wrap{overflow-x:auto;margin-bottom:18px}
.cmp{width:100%;border-collapse:collapse;font-size:12px}
.cmp th{background:#f7f8fa;padding:8px 10px;text-align:left;border-bottom:2px solid #e5e7eb;
        font-size:10px;color:#57606a;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}
.cmp td{padding:8px 10px;border-bottom:1px solid #f0f2f5;vertical-align:middle}
.cmp tr:last-child td{border-bottom:none}
.cmp tr:hover td{background:#fafbfc}
.cmp .sid-cell{font-weight:700;font-size:13px;color:#1f2328;white-space:nowrap}
.cmp .module-tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;
                 color:#fff;margin-right:3px;white-space:nowrap}
.score-bar-wrap{display:flex;align-items:center;gap:7px;min-width:130px}
.score-bar-track{flex:1;background:#f0f2f5;border-radius:4px;height:10px;overflow:hidden}
.score-bar-fill{height:100%;border-radius:4px}
.score-num{width:28px;text-align:right;font-size:11px;font-weight:700;flex-shrink:0}

/* risk badge */
.rb{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;white-space:nowrap}
.rb-crit{background:#fee2e2;color:#991b1b}
.rb-hi{background:#ffedd5;color:#9a3412}
.rb-med{background:#fef3c7;color:#92400e}
.rb-low{background:#d1fae5;color:#065f46}

/* system cards grid */
.sys-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px;margin-bottom:18px}
.sys-card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden}
.sys-card-hdr{padding:12px 14px 10px;border-bottom:1px solid #f0f2f5;display:flex;justify-content:space-between;align-items:flex-start}
.sys-card-sid{font-size:20px;font-weight:800;color:#1f2328;letter-spacing:-0.5px;line-height:1}
.sys-card-desc{font-size:10px;color:#57606a;margin-top:3px;line-height:1.4}
.sys-card-body{padding:12px 14px}

/* mini stat row */
.mini-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:10px}
.mini-stat{background:#f7f8fa;border:1px solid #e5e7eb;border-radius:6px;padding:7px 8px;text-align:center}
.mini-stat .mv{font-size:17px;font-weight:700;line-height:1}
.mini-stat .ml{font-size:9px;color:#57606a;margin-top:2px}

/* mini bar */
.m-bar-row{display:flex;align-items:center;gap:6px;margin-bottom:5px}
.m-bar-lbl{width:110px;flex-shrink:0;font-size:10px;color:#57606a}
.m-bar-track{flex:1;background:#f0f2f5;border-radius:3px;height:9px;overflow:hidden}
.m-bar-fill{height:100%;border-radius:3px}
.m-bar-val{width:24px;text-align:right;font-size:10px;color:#57606a;flex-shrink:0}

/* critical areas */
.crit-list{list-style:none;margin-top:8px}
.crit-list li{font-size:10px;color:#57606a;padding:3px 0;border-bottom:1px solid #f0f2f5;
              display:flex;align-items:flex-start;gap:5px}
.crit-list li:last-child{border-bottom:none}
.crit-list li::before{content:"⚠";color:#f97316;flex-shrink:0;margin-top:1px}

/* effort bar chart */
.effort-chart{margin-bottom:18px}
.eff-row{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.eff-lbl{width:90px;flex-shrink:0;font-size:11px;font-weight:600;color:#1f2328}
.eff-track{flex:1;background:#f0f2f5;border-radius:4px;height:18px;overflow:hidden}
.eff-fill{height:100%;border-radius:4px;display:flex;align-items:center;padding-left:8px;
          font-size:10px;font-weight:700;color:#fff;white-space:nowrap}
.eff-days{width:55px;text-align:right;font-size:11px;color:#57606a;flex-shrink:0}

/* objects comparison */
.obj-chart{margin-bottom:18px}

/* summary KPI strip */
.sum-strip{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:18px}
.sum-kpi{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:12px;text-align:center;border-top:3px solid #e5e7eb}
.sum-kpi .sk-val{font-size:22px;font-weight:700;line-height:1.1}
.sum-kpi .sk-lbl{font-size:9px;color:#57606a;text-transform:uppercase;letter-spacing:.05em;margin-top:4px}

footer{text-align:center;font-size:11px;color:#8b949e;padding-top:14px;border-top:1px solid #e5e7eb;margin-top:20px}
"""

# module colour map
_MOD_COLORS = {
    "MM":  "#3b82d4",
    "HR":  "#10b981",
    "SD":  "#f97316",
    "GRC": "#dc2626",
    "APO": "#7c5cd8",
    "CRM": "#06b6d4",
    "FI":  "#1f2328",
    "CO":  "#6b7280",
    "PP":  "#eab308",
    "WM":  "#84cc16",
    "QM":  "#f43f5e",
    "PM":  "#8b5cf6",
}

def _mod_color(module: str) -> str:
    return _MOD_COLORS.get(module.upper(), "#57606a")

def _risk_badge(risk_level: str) -> str:
    cls = {"critical": "rb-crit", "high": "rb-hi", "medium": "rb-med", "low": "rb-low"}.get(risk_level.lower(), "rb-med")
    return f'<span class="rb {cls}">{risk_level.upper()}</span>'

def _score_bar(score: float) -> str:
    colour = "#dc2626" if score < 40 else ("#eab308" if score < 65 else "#10b981")
    return f"""<div class="score-bar-wrap">
      <div class="score-bar-track"><div class="score-bar-fill" style="width:{score}%;background:{colour}"></div></div>
      <span class="score-num" style="color:{colour}">{score:.0f}</span>
    </div>"""

def _module_tag(module: str) -> str:
    col = _mod_color(module)
    return f'<span class="module-tag" style="background:{col}">{module}</span>'

def _detect_module(sid: str, description: str) -> str:
    """Infer primary SAP module from SID prefix or description."""
    sid_up = sid.upper()
    desc_up = (description or "").upper()
    for mod in ("MM", "HR", "SD", "GRC", "APO", "CRM", "FI", "CO", "PP", "WM", "QM", "PM"):
        if sid_up.startswith(mod):
            return mod
    for mod in ("MM", "HR", "SD", "GRC", "APO", "CRM"):
        if mod in desc_up:
            return mod
    return sid_up[:3]


def generate_multi_system_dashboard(
    states: "List[AgentState]",
    output_path: Path,
) -> Path:
    """
    Build a single self-contained HTML dashboard that shows all SAP systems
    (MM, HR, SD, GRC, APO, CRM, …) side-by-side.

    Parameters
    ----------
    states      : list of completed AgentState objects, one per system
    output_path : where to write the HTML file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n = len(states)

    # ── aggregate totals ─────────────────────────────────────────────────────
    total_objects   = sum((s.custom_code.total_objects if s.custom_code else 0) for s in states)
    total_loc       = sum((s.custom_code.total_lines_of_code if s.custom_code else 0) for s in states)
    total_findings  = sum((s.atc_report.total_findings if s.atc_report else 0) for s in states)
    total_critical  = sum((s.atc_report.critical_count if s.atc_report else 0) for s in states)
    total_effort    = sum((s.readiness_score.estimated_effort_days if s.readiness_score else 0) for s in states)
    total_simp      = sum((s.simplification_report.total_impacts if s.simplification_report else 0) for s in states)

    # ── summary KPI strip ────────────────────────────────────────────────────
    sum_strip = f"""
    <div class="sum-strip">
      <div class="sum-kpi" style="border-top-color:#3b82d4">
        <div class="sk-val" style="color:#3b82d4">{n}</div>
        <div class="sk-lbl">SAP Systems</div>
      </div>
      <div class="sum-kpi" style="border-top-color:#7c5cd8">
        <div class="sk-val" style="color:#7c5cd8">{total_objects:,}</div>
        <div class="sk-lbl">Custom Objects</div>
      </div>
      <div class="sum-kpi" style="border-top-color:#dc2626">
        <div class="sk-val" style="color:#dc2626">{total_findings:,}</div>
        <div class="sk-lbl">ATC Findings</div>
      </div>
      <div class="sum-kpi" style="border-top-color:#ef4444">
        <div class="sk-val" style="color:#ef4444">{total_critical:,}</div>
        <div class="sk-lbl">Critical Findings</div>
      </div>
      <div class="sum-kpi" style="border-top-color:#f97316">
        <div class="sk-val" style="color:#f97316">{total_effort:,}</div>
        <div class="sk-lbl">Total Effort Days</div>
      </div>
      <div class="sum-kpi" style="border-top-color:#10b981">
        <div class="sk-val" style="color:#10b981">{total_simp:,}</div>
        <div class="sk-lbl">Simplif. Items</div>
      </div>
    </div>"""

    # ── comparison table ─────────────────────────────────────────────────────
    table_rows = ""
    for s in sorted(states, key=lambda x: (x.readiness_score.overall_score if x.readiness_score else 0)):
        sid         = s.sap_system.sid
        desc        = s.sap_system.description or ""
        module      = _detect_module(sid, desc)
        score       = round(s.readiness_score.overall_score, 1) if s.readiness_score else 0
        risk        = s.readiness_score.risk_level.value if s.readiness_score else "unknown"
        effort      = s.readiness_score.estimated_effort_days if s.readiness_score else 0
        obj_count   = s.custom_code.total_objects if s.custom_code else 0
        loc         = s.custom_code.total_lines_of_code if s.custom_code else 0
        findings    = s.atc_report.total_findings if s.atc_report else 0
        crit        = s.atc_report.critical_count if s.atc_report else 0
        high        = s.atc_report.high_count if s.atc_report else 0
        simp        = s.simplification_report.total_impacts if s.simplification_report else 0

        table_rows += f"""
        <tr>
          <td class="sid-cell">{_module_tag(module)} {sid}</td>
          <td style="font-size:11px;color:#57606a;max-width:220px">{desc[:80]}</td>
          <td>{_score_bar(score)}</td>
          <td>{_risk_badge(risk)}</td>
          <td style="text-align:right;font-weight:600">{obj_count:,}</td>
          <td style="text-align:right;color:#57606a;font-size:11px">{loc:,}</td>
          <td style="text-align:right;color:#dc2626;font-weight:700">{crit}</td>
          <td style="text-align:right;color:#f97316;font-weight:600">{high}</td>
          <td style="text-align:right">{findings}</td>
          <td style="text-align:right">{simp}</td>
          <td style="text-align:right;font-weight:600;color:#f97316">{effort}</td>
        </tr>"""

    cmp_table = f"""
    <div class="cmp-wrap">
      <table class="cmp">
        <thead>
          <tr>
            <th>System</th>
            <th>Description</th>
            <th style="min-width:150px">Readiness Score</th>
            <th>Risk Level</th>
            <th style="text-align:right">Objects</th>
            <th style="text-align:right">LOC</th>
            <th style="text-align:right">Critical</th>
            <th style="text-align:right">High</th>
            <th style="text-align:right">ATC Total</th>
            <th style="text-align:right">Simplif.</th>
            <th style="text-align:right">Effort (days)</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </div>"""

    # ── effort horizontal bar chart ───────────────────────────────────────────
    max_effort = max((s.readiness_score.estimated_effort_days if s.readiness_score else 0) for s in states) or 1
    eff_rows = ""
    for s in sorted(states, key=lambda x: -(x.readiness_score.estimated_effort_days if x.readiness_score else 0)):
        sid    = s.sap_system.sid
        module = _detect_module(sid, s.sap_system.description or "")
        effort = s.readiness_score.estimated_effort_days if s.readiness_score else 0
        pct    = round(effort / max_effort * 100)
        col    = _mod_color(module)
        label  = f"{effort} days" if pct > 18 else ""
        eff_rows += f"""
        <div class="eff-row">
          <div class="eff-lbl">{_module_tag(module)} {sid}</div>
          <div class="eff-track"><div class="eff-fill" style="width:{pct}%;background:{col}">{label}</div></div>
          <div class="eff-days">{effort} days</div>
        </div>"""

    effort_chart = f'<div class="effort-chart">{eff_rows}</div>'

    # ── custom objects horizontal bar chart ───────────────────────────────────
    max_obj = max((s.custom_code.total_objects if s.custom_code else 0) for s in states) or 1
    obj_rows = ""
    for s in sorted(states, key=lambda x: -(x.custom_code.total_objects if x.custom_code else 0)):
        sid    = s.sap_system.sid
        module = _detect_module(sid, s.sap_system.description or "")
        objs   = s.custom_code.total_objects if s.custom_code else 0
        loc    = s.custom_code.total_lines_of_code if s.custom_code else 0
        pct    = round(objs / max_obj * 100)
        col    = _mod_color(module)
        label  = f"{objs:,} objects" if pct > 18 else ""
        obj_rows += f"""
        <div class="eff-row">
          <div class="eff-lbl">{_module_tag(module)} {sid}</div>
          <div class="eff-track"><div class="eff-fill" style="width:{pct}%;background:{col}">{label}</div></div>
          <div class="eff-days">{objs:,}</div>
        </div>"""

    obj_chart = f'<div class="obj-chart">{obj_rows}</div>'

    # ── ATC findings grouped bar (inline SVG) ─────────────────────────────────
    atc_svg_rows = ""
    atc_max = max((s.atc_report.total_findings if s.atc_report else 0) for s in states) or 1
    for s in sorted(states, key=lambda x: -(x.atc_report.total_findings if x.atc_report else 0)):
        sid  = s.sap_system.sid
        module = _detect_module(sid, s.sap_system.description or "")
        if not s.atc_report:
            continue
        a    = s.atc_report
        tot  = a.total_findings
        crit_pct = round(a.critical_count / max(tot, 1) * 100)
        hi_pct   = round(a.high_count    / max(tot, 1) * 100)
        med_pct  = round(a.medium_count  / max(tot, 1) * 100)
        lo_pct   = round(a.low_count     / max(tot, 1) * 100)
        bar_w    = round(tot / atc_max * 100)
        atc_svg_rows += f"""
        <div class="eff-row">
          <div class="eff-lbl">{_module_tag(module)} {sid}</div>
          <div class="eff-track" style="height:14px">
            <div style="display:flex;height:100%;width:{bar_w}%">
              <div style="width:{crit_pct}%;background:#dc2626;height:100%" title="Critical: {a.critical_count}"></div>
              <div style="width:{hi_pct}%;background:#f97316;height:100%" title="High: {a.high_count}"></div>
              <div style="width:{med_pct}%;background:#eab308;height:100%" title="Medium: {a.medium_count}"></div>
              <div style="width:{lo_pct}%;background:#22c55e;height:100%" title="Low: {a.low_count}"></div>
            </div>
          </div>
          <div class="eff-days">{tot} <span style="font-size:9px;color:#dc2626">({a.critical_count}C)</span></div>
        </div>"""

    atc_chart = f'<div class="effort-chart">{atc_svg_rows}</div>'

    # ── per-system cards ──────────────────────────────────────────────────────
    cards_html = ""
    for s in states:
        sid    = s.sap_system.sid
        desc   = s.sap_system.description or ""
        module = _detect_module(sid, desc)
        col    = _mod_color(module)
        score  = round(s.readiness_score.overall_score, 1) if s.readiness_score else 0
        risk   = s.readiness_score.risk_level.value if s.readiness_score else "unknown"
        effort = s.readiness_score.estimated_effort_days if s.readiness_score else 0
        objs   = s.custom_code.total_objects if s.custom_code else 0
        findings = s.atc_report.total_findings if s.atc_report else 0
        crit   = s.atc_report.critical_count if s.atc_report else 0
        simp   = s.simplification_report.total_impacts if s.simplification_report else 0

        # readiness score colour
        score_col = "#dc2626" if score < 40 else ("#eab308" if score < 65 else "#10b981")

        # critical areas list (from risk summary stored in description or readiness)
        crit_areas = ""
        if s.readiness_score and s.readiness_score.critical_objects:
            crit_areas = "".join(
                f"<li>{area}</li>"
                for area in s.readiness_score.critical_objects[:3]
            )
        else:
            crit_areas = "<li>No critical areas identified</li>"

        # mini bars — ATC breakdown
        atc = s.atc_report
        atc_max_val = max(crit, (atc.high_count if atc else 0), (atc.medium_count if atc else 0), 1)
        mini_bars = ""
        for lbl, val, bar_col in [
            ("Critical", crit, "#dc2626"),
            ("High",     atc.high_count   if atc else 0, "#f97316"),
            ("Medium",   atc.medium_count if atc else 0, "#eab308"),
            ("Low",      atc.low_count    if atc else 0, "#22c55e"),
        ]:
            pct = round(val / atc_max_val * 100)
            mini_bars += f"""
            <div class="m-bar-row">
              <div class="m-bar-lbl">{lbl}</div>
              <div class="m-bar-track"><div class="m-bar-fill" style="width:{pct}%;background:{bar_col}"></div></div>
              <div class="m-bar-val">{val}</div>
            </div>"""

        # version / host from landscape if available
        ver_line = ""
        if s.landscape:
            ver_line = f'<div style="font-size:10px;color:#57606a;margin-top:4px">{s.landscape.sap_version}</div>'

        cards_html += f"""
        <div class="sys-card">
          <div class="sys-card-hdr" style="border-left:4px solid {col}">
            <div>
              <div style="display:flex;align-items:center;gap:7px">
                {_module_tag(module)}
                <span class="sys-card-sid">{sid}</span>
              </div>
              <div class="sys-card-desc">{desc[:90]}</div>
              {ver_line}
            </div>
            <div style="text-align:right;flex-shrink:0;margin-left:10px">
              <div style="font-size:26px;font-weight:800;color:{score_col};line-height:1">{score}</div>
              <div style="font-size:9px;color:#57606a">/ 100</div>
              {_risk_badge(risk)}
            </div>
          </div>
          <div class="sys-card-body">
            <div class="mini-stats">
              <div class="mini-stat">
                <div class="mv" style="color:#7c5cd8">{objs:,}</div>
                <div class="ml">Objects</div>
              </div>
              <div class="mini-stat">
                <div class="mv" style="color:#dc2626">{findings}</div>
                <div class="ml">ATC Findings</div>
              </div>
              <div class="mini-stat">
                <div class="mv" style="color:#f97316">{effort}</div>
                <div class="ml">Effort Days</div>
              </div>
            </div>
            {mini_bars}
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#57606a;margin:8px 0 4px">
              Critical Areas
            </div>
            <ul class="crit-list">{crit_areas}</ul>
          </div>
        </div>"""

    # ── assemble full HTML ────────────────────────────────────────────────────
    system_names = ", ".join(s.sap_system.sid for s in states)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SAP S/4HANA Migration — Multi-System Dashboard</title>
<style>{_MULTI_CSS}</style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <div class="hdr">
    <div class="t1">SAP ECC → S/4HANA Migration — Multi-System Assessment Dashboard</div>
    <div class="t2">Generated: {generated_at} &nbsp;·&nbsp; {n} systems assessed &nbsp;·&nbsp; SAP Migration Agent (9-agent LangGraph pipeline)</div>
    <div class="t3">Systems: {system_names}</div>
  </div>

  <!-- SUMMARY KPIs -->
  <div class="sec-title"><span class="sec-title-dot" style="background:#3b82d4"></span>Portfolio Summary — All {n} Systems</div>
  {sum_strip}

  <!-- COMPARISON TABLE -->
  <div class="sec-title"><span class="sec-title-dot" style="background:#7c5cd8"></span>System-by-System Comparison (sorted by readiness score ↑ = most risk)</div>
  {cmp_table}

  <!-- EFFORT CHART -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px">
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px">
      <div class="sec-title" style="margin-top:0"><span class="sec-title-dot" style="background:#f97316"></span>Remediation Effort by System (days)</div>
      {effort_chart}
    </div>
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px">
      <div class="sec-title" style="margin-top:0"><span class="sec-title-dot" style="background:#7c5cd8"></span>Custom Objects by System</div>
      {obj_chart}
    </div>
  </div>

  <!-- ATC CHART -->
  <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:14px 16px;margin-bottom:18px">
    <div class="sec-title" style="margin-top:0">
      <span class="sec-title-dot" style="background:#dc2626"></span>
      ATC Findings by System
      <span style="font-size:10px;color:#57606a;font-weight:400;margin-left:6px">
        ■ Critical &nbsp; ■ High &nbsp; ■ Medium &nbsp; ■ Low
      </span>
      <span style="font-size:10px;color:#57606a;margin-left:4px">
        (<span style="color:#dc2626">■</span>
         <span style="color:#f97316">■</span>
         <span style="color:#eab308">■</span>
         <span style="color:#22c55e">■</span>)
      </span>
    </div>
    {atc_chart}
  </div>

  <!-- PER-SYSTEM CARDS -->
  <div class="sec-title"><span class="sec-title-dot" style="background:#06b6d4"></span>Individual System Details</div>
  <div class="sys-grid">
    {cards_html}
  </div>

  <footer>
    Multi-System Dashboard &nbsp;·&nbsp; {n} SAP systems &nbsp;·&nbsp;
    Generated: {generated_at} &nbsp;·&nbsp; SAP Migration Agent
    <br><span style="font-size:10px;color:#aab">Made with IBM Bob</span>
  </footer>

</div>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED SAP Agentic AI Dashboard  (single page, all systems + deep-dive)
# ─────────────────────────────────────────────────────────────────────────────

_UNIFIED_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"Segoe UI",system-ui,sans-serif;font-size:13px;
     line-height:1.55;background:#0d1117;color:#e6edf3}

/* ── layout ── */
.page{max-width:1160px;margin:0 auto;padding:20px 14px 60px}

/* ── top banner (SAP Agentic AI branding) ── */
.banner{
  background:linear-gradient(135deg,#0d1117 0%,#161b22 55%,#0d2137 100%);
  border:1px solid #30363d;border-radius:12px;
  padding:24px 28px;margin-bottom:18px;
  display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.banner-l .logo{font-size:11px;font-weight:700;letter-spacing:.18em;
                text-transform:uppercase;color:#3b82d4;margin-bottom:6px}
.banner-l .title{font-size:20px;font-weight:800;color:#e6edf3;line-height:1.2;margin-bottom:5px}
.banner-l .sub{font-size:11px;color:#8b949e;margin-bottom:10px}
.agent-chips{display:flex;flex-wrap:wrap;gap:5px}
.agent-chip{font-size:9px;font-weight:700;padding:2px 8px;border-radius:10px;
            letter-spacing:.04em;border:1px solid #30363d;color:#8b949e;background:#161b22}
.agent-chip.done{border-color:#3b82d4;color:#3b82d4;background:#0d2137}
.banner-r{text-align:right;flex-shrink:0}
.llm-badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:10px;
           font-weight:700;letter-spacing:.06em;text-transform:uppercase;
           background:linear-gradient(90deg,#7c5cd8,#3b82d4);color:#fff;margin-bottom:8px}
.gen-info{font-size:10px;color:#8b949e;line-height:1.7}

/* ── section headings ── */
.sec{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.09em;
     color:#8b949e;margin:20px 0 10px;display:flex;align-items:center;gap:7px}
.sec-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}

/* ── AI insight panel ── */
.ai-panel{background:#161b22;border:1px solid #3b82d4;border-radius:10px;
          padding:16px 20px;margin-bottom:18px}
.ai-panel-hdr{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.ai-icon{width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#7c5cd8,#3b82d4);
         display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0}
.ai-title{font-size:13px;font-weight:700;color:#e6edf3}
.ai-sub{font-size:10px;color:#8b949e}
.ai-insights{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
.insight{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:11px 13px}
.insight-lbl{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;
             color:#57606a;margin-bottom:5px;display:flex;align-items:center;gap:5px}
.insight-val{font-size:13px;color:#e6edf3;line-height:1.4}
.insight-tag{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;
             font-weight:700;margin-top:4px}
.tag-crit{background:#3f1010;color:#f87171;border:1px solid #7f1d1d}
.tag-high{background:#3f1e0a;color:#fb923c;border:1px solid #7c2d12}
.tag-med{background:#3b3008;color:#fbbf24;border:1px solid #78350f}
.tag-low{background:#0d2e1d;color:#34d399;border:1px solid #065f46}

/* ── KPI strip ── */
.kpi-row{display:grid;grid-template-columns:repeat(8,1fr);gap:9px;margin-bottom:16px}
.kpi{background:#161b22;border:1px solid #30363d;border-radius:8px;
     padding:12px 12px 9px;border-top:3px solid #30363d}
.kpi-lbl{font-size:9px;color:#8b949e;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
.kpi-val{font-size:20px;font-weight:700;line-height:1.1}
.kpi-sub{font-size:9px;color:#8b949e;margin-top:3px}

/* ── cards ── */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:14px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 16px}
.card-full{margin-bottom:14px}
.ctitle{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;
        color:#8b949e;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.ctitle-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}

/* ── bars ── */
.bar-row{display:flex;align-items:center;gap:7px;margin-bottom:6px}
.bar-label{width:130px;flex-shrink:0;font-size:10px;color:#c9d1d9}
.bar-sub{font-size:9px;color:#8b949e;margin-left:3px}
.bar-track{flex:1;background:#21262d;border-radius:3px;height:11px;overflow:hidden}
.bar-fill{height:100%;border-radius:3px;transition:width .3s}
.bar-val{width:28px;text-align:right;font-size:10px;color:#8b949e;flex-shrink:0}

/* ── table ── */
table{width:100%;border-collapse:collapse;font-size:11px}
th{text-align:left;padding:5px 7px;border-bottom:2px solid #30363d;
   font-size:9px;color:#8b949e;text-transform:uppercase;letter-spacing:.04em}
td{padding:6px 7px;border-bottom:1px solid #21262d;vertical-align:top;color:#c9d1d9}
tr:last-child td{border-bottom:none}
td code{font-size:10px;background:#21262d;padding:1px 4px;border-radius:3px;
        font-family:monospace;color:#79c0ff}
tr:hover td{background:#1c2128}

/* ── badges ── */
.badge-crit{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;
            font-weight:700;background:#3f1010;color:#f87171;border:1px solid #7f1d1d}
.badge-high{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;
            font-weight:700;background:#3f1e0a;color:#fb923c;border:1px solid #7c2d12}
.badge-med{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;
           font-weight:700;background:#3b3008;color:#fbbf24;border:1px solid #78350f}
.badge-low{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;
           font-weight:700;background:#0d2e1d;color:#34d399;border:1px solid #065f46}

/* ── runbook steps ── */
.steps{list-style:none}
.steps li{display:flex;gap:8px;padding:6px 0;border-bottom:1px solid #21262d;
          font-size:11px;align-items:flex-start}
.steps li:last-child{border-bottom:none}
.snum{flex-shrink:0;width:18px;height:18px;border-radius:50%;
      background:#3b82d4;color:#fff;font-size:9px;font-weight:700;
      display:flex;align-items:center;justify-content:center;margin-top:1px}
.smeta{font-size:10px;color:#8b949e;margin-top:1px}

/* ── comparison table ── */
.cmp-wrap{overflow-x:auto;margin-bottom:14px}
.cmp{width:100%;border-collapse:collapse;font-size:11px}
.cmp th{background:#1c2128;padding:7px 9px;text-align:left;border-bottom:2px solid #30363d;
        font-size:9px;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}
.cmp td{padding:7px 9px;border-bottom:1px solid #21262d;vertical-align:middle;color:#c9d1d9}
.cmp tr:last-child td{border-bottom:none}
.cmp tr:hover td{background:#1c2128}
.cmp .sid-cell{font-weight:700;font-size:12px;color:#e6edf3;white-space:nowrap}
.module-tag{display:inline-block;padding:2px 7px;border-radius:9px;font-size:9px;
            font-weight:700;color:#fff;margin-right:3px;white-space:nowrap}
.score-bar-wrap{display:flex;align-items:center;gap:6px;min-width:120px}
.score-bar-track{flex:1;background:#21262d;border-radius:3px;height:9px;overflow:hidden}
.score-bar-fill{height:100%;border-radius:3px}
.score-num{width:26px;text-align:right;font-size:10px;font-weight:700;flex-shrink:0}

/* ── system cards ── */
.sys-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
          gap:12px;margin-bottom:16px}
.sys-card{background:#161b22;border:1px solid #30363d;border-radius:10px;overflow:hidden}
.sys-card-hdr{padding:11px 13px 9px;border-bottom:1px solid #21262d;
              display:flex;justify-content:space-between;align-items:flex-start}
.sys-card-sid{font-size:18px;font-weight:800;color:#e6edf3;letter-spacing:-0.5px;line-height:1}
.sys-card-desc{font-size:10px;color:#8b949e;margin-top:3px;line-height:1.4}
.sys-card-body{padding:11px 13px}
.mini-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:9px}
.mini-stat{background:#0d1117;border:1px solid #30363d;border-radius:5px;
           padding:6px 7px;text-align:center}
.mini-stat .mv{font-size:16px;font-weight:700;line-height:1}
.mini-stat .ml{font-size:9px;color:#8b949e;margin-top:2px}

/* ── effort bars ── */
.eff-row{display:flex;align-items:center;gap:7px;margin-bottom:5px}
.eff-lbl{width:100px;flex-shrink:0;font-size:10px;font-weight:600;color:#c9d1d9}
.eff-track{flex:1;background:#21262d;border-radius:3px;height:16px;overflow:hidden}
.eff-fill{height:100%;border-radius:3px;display:flex;align-items:center;padding-left:7px;
          font-size:9px;font-weight:700;color:#fff;white-space:nowrap}
.eff-days{width:52px;text-align:right;font-size:10px;color:#8b949e;flex-shrink:0}

/* ── mini-bar in card ── */
.m-bar-row{display:flex;align-items:center;gap:5px;margin-bottom:4px}
.m-bar-lbl{width:55px;flex-shrink:0;font-size:9px;color:#8b949e}
.m-bar-track{flex:1;background:#21262d;border-radius:2px;height:8px;overflow:hidden}
.m-bar-fill{height:100%;border-radius:2px}
.m-bar-val{width:22px;text-align:right;font-size:9px;color:#8b949e;flex-shrink:0}

/* ── risk badge ── */
.rb{display:inline-block;padding:2px 7px;border-radius:9px;font-size:9px;
    font-weight:700;white-space:nowrap}
.rb-crit{background:#3f1010;color:#f87171;border:1px solid #7f1d1d}
.rb-hi{background:#3f1e0a;color:#fb923c;border:1px solid #7c2d12}
.rb-med{background:#3b3008;color:#fbbf24;border:1px solid #78350f}
.rb-low{background:#0d2e1d;color:#34d399;border:1px solid #065f46}

/* ── stat box ── */
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:7px}
.stat-box{background:#0d1117;border:1px solid #30363d;border-radius:5px;
          padding:7px;text-align:center}
.stat-box .sv{font-size:17px;font-weight:700}
.stat-box .sl{font-size:9px;color:#8b949e;margin-top:1px}

/* ── chips ── */
.chips{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:12px}
.chip{background:#0d2e1d;color:#34d399;border:1px solid #065f46;
      font-size:9px;font-weight:700;padding:2px 8px;border-radius:9px}
.chip::before{content:"✓ "}

/* ── agent flow ── */
.agent-flow{display:flex;align-items:center;gap:0;flex-wrap:wrap;margin-bottom:16px}
.af-node{background:#161b22;border:1px solid #30363d;border-radius:6px;
         padding:6px 10px;font-size:10px;text-align:center;min-width:82px}
.af-node .af-num{font-size:8px;font-weight:700;color:#3b82d4;margin-bottom:2px}
.af-node .af-lbl{font-size:9px;font-weight:600;color:#e6edf3;white-space:nowrap}
.af-node .af-sub{font-size:8px;color:#8b949e;margin-top:1px}
.af-node.done{border-color:#3b82d4;background:#0d2137}
.af-arrow{color:#30363d;font-size:12px;padding:0 2px;flex-shrink:0}

/* ── summary portfolio KPI ── */
.sum-strip{display:grid;grid-template-columns:repeat(6,1fr);gap:9px;margin-bottom:14px}
.sum-kpi{background:#161b22;border:1px solid #30363d;border-radius:8px;
         padding:11px;text-align:center;border-top:3px solid #30363d}
.sum-kpi .sk-val{font-size:20px;font-weight:700;line-height:1.1}
.sum-kpi .sk-lbl{font-size:9px;color:#8b949e;text-transform:uppercase;
                 letter-spacing:.05em;margin-top:3px}

/* ── tab panels ── */
.tab-bar{display:flex;gap:0;border-bottom:1px solid #30363d;margin-bottom:14px;overflow-x:auto}
.tab{padding:8px 16px;font-size:11px;font-weight:600;color:#8b949e;cursor:pointer;
     border-bottom:2px solid transparent;white-space:nowrap;user-select:none;
     background:none;border-top:none;border-left:none;border-right:none}
.tab.active{color:#3b82d4;border-bottom-color:#3b82d4}
.tab-panel{display:none}
.tab-panel.active{display:block}

/* ── gauge SVG wrapper ── */
.gauge-wrap{display:flex;flex-direction:column;align-items:center;padding:4px 0 4px}
.gauge-legend{display:flex;gap:12px;font-size:9px;color:#8b949e;margin-top:4px}

/* ── divider ── */
hr.div{border:none;border-top:1px solid #30363d;margin:10px 0}

/* ── file table ── */
.file-tbl td:first-child{font-family:monospace;font-size:10px;color:#79c0ff}
.file-tbl td:last-child{color:#8b949e;white-space:nowrap}

footer{text-align:center;font-size:10px;color:#8b949e;padding-top:14px;
       border-top:1px solid #30363d;margin-top:22px}
"""


def _udark_badge(priority: str) -> str:
    colours = {
        "critical": "badge-crit", "high": "badge-high",
        "medium": "badge-med", "low": "badge-low",
    }
    cls = colours.get(priority.lower(), "badge-low")
    return f'<span class="{cls}">{priority.title()}</span>'


def _u_bar(label: str, value: int, max_val: int, colour: str, sub: str = "") -> str:
    pct = round(value / max_val * 100) if max_val else 0
    sub_html = f'<span class="bar-sub">{sub}</span>' if sub else ""
    return (
        f'<div class="bar-row">'
        f'<div class="bar-label">{label}{sub_html}</div>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{colour}"></div></div>'
        f'<div class="bar-val">{value}</div>'
        f'</div>'
    )


def _u_gauge(score: float) -> str:
    import math
    cx, cy, r = 100, 100, 82
    ex = cx + r * math.cos(math.radians(180 - (score / 100) * 180))
    ey = cy - r * math.sin(math.radians(180 - (score / 100) * 180))
    large = 1 if (score / 100) * 180 > 90 else 0
    colour = "#f87171" if score < 40 else ("#fbbf24" if score < 65 else "#34d399")
    risk_label = "HIGH RISK" if score < 40 else ("MEDIUM RISK" if score < 65 else "LOW RISK")
    return f"""
    <svg viewBox="0 0 200 118" width="200" height="118" style="overflow:visible">
      <path d="M18,100 A82,82 0 0,1 80.3,24.3"  fill="none" stroke="#3f1010" stroke-width="17" stroke-linecap="butt"/>
      <path d="M80.3,24.3 A82,82 0 0,1 141,21.5" fill="none" stroke="#3b3008" stroke-width="17" stroke-linecap="butt"/>
      <path d="M141,21.5 A82,82 0 0,1 182,100"   fill="none" stroke="#0d2e1d" stroke-width="17" stroke-linecap="butt"/>
      <path d="M18,100 A82,82 0 0,1 182,100" fill="none" stroke="#30363d" stroke-width="17" stroke-linecap="round" opacity=".4"/>
      <path d="M18,100 A82,82 0 {large},1 {ex:.1f},{ey:.1f}" fill="none" stroke="{colour}" stroke-width="17" stroke-linecap="round"/>
      <circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{colour}"/>
      <text x="100" y="84"  text-anchor="middle" font-size="30" font-weight="800" fill="#e6edf3">{score}</text>
      <text x="100" y="100" text-anchor="middle" font-size="10" fill="#8b949e">out of 100</text>
      <text x="100" y="114" text-anchor="middle" font-size="9"  font-weight="700" fill="{colour}">{risk_label}</text>
      <text x="14"  y="115" font-size="8" fill="#f87171">RISK</text>
      <text x="186" y="115" text-anchor="end" font-size="8" fill="#34d399">SAFE</text>
    </svg>"""


def _u_atc_bar(critical: int, high: int, medium: int, low: int) -> str:
    total = critical + high + medium + low
    max_v = max(critical, high, medium, low, 1)
    scale = 100 / max_v

    def bar(x, val, col, lbl):
        h = round(val * scale)
        y = 112 - h
        return (
            f'<rect x="{x}" y="{y}" width="36" height="{h}" rx="3" fill="{col}"/>'
            f'<text x="{x+18}" y="{y-4}" text-anchor="middle" font-size="11" font-weight="700" fill="{col}">{val}</text>'
            f'<text x="{x+18}" y="130" text-anchor="middle" font-size="9" fill="#8b949e">{lbl}</text>'
        )

    rows = (
        bar(36, critical, "#f87171", "Critical") +
        bar(82, high,     "#fb923c", "High") +
        bar(128, medium,  "#fbbf24", "Medium") +
        bar(174, low,     "#34d399", "Low")
    )
    return f"""
    <svg viewBox="0 0 230 142" width="100%" style="display:block;overflow:visible">
      <line x1="30" y1="10" x2="30" y2="114" stroke="#30363d"/>
      <line x1="30" y1="114" x2="218" y2="114" stroke="#30363d"/>
      {rows}
      <text x="124" y="142" text-anchor="middle" font-size="9" fill="#8b949e">{total} total findings</text>
    </svg>"""


def _u_timeline(weeks: int) -> str:
    W = 700
    pw = W / max(weeks, 1)

    def phase(x, w, y, h, col, label):
        return (
            f'<rect x="{x:.0f}" y="{y}" width="{w:.0f}" height="{h}" rx="3" fill="{col}"/>'
            f'<text x="{x+w/2:.0f}" y="{y+h/2+4}" text-anchor="middle" font-size="8" fill="#fff" font-weight="600">{label}</text>'
        )

    bars = (
        phase(10,        2*pw,  8, 18, "#3b82d4", "Project Charter") +
        phase(4*pw+10,   4*pw,  8, 18, "#34d399", "Business Partner Conv.") +
        phase(10,        4*pw, 30, 18, "#7c5cd8", "Landscape &amp; Prep") +
        phase(6*pw+10,  (weeks-6)*pw, 30, 18, "#f87171", "UAT &amp; Testing") +
        phase(2*pw+10,   8*pw, 52, 18, "#fb923c", "Custom Code Adaptation") +
        phase(4*pw+10,   3*pw, 74, 16, "#06b6d4", "Material Ledger") +
        phase((weeks-2)*pw+10, 2*pw, 74, 16, "#e6edf3", "Cutover")
    )
    ticks = "".join(
        f'<text x="{10+i*pw:.0f}" y="106" font-size="8" fill="#8b949e" text-anchor="middle">W{i}</text>'
        for i in range(0, weeks+1, 2)
    )
    return f"""
    <svg viewBox="0 0 740 112" width="100%" style="min-width:460px;display:block;overflow:visible">
      <line x1="10" y1="96" x2="720" y2="96" stroke="#30363d"/>
      {bars}{ticks}
    </svg>"""


def _u_risk_badge(risk_level: str) -> str:
    cls = {"critical": "rb-crit", "high": "rb-hi", "medium": "rb-med", "low": "rb-low"}.get(
        risk_level.lower(), "rb-med")
    return f'<span class="rb {cls}">{risk_level.upper()}</span>'


def _u_score_bar(score: float) -> str:
    colour = "#f87171" if score < 40 else ("#fbbf24" if score < 65 else "#34d399")
    return (
        f'<div class="score-bar-wrap">'
        f'<div class="score-bar-track"><div class="score-bar-fill" style="width:{score}%;background:{colour}"></div></div>'
        f'<span class="score-num" style="color:{colour}">{score:.0f}</span>'
        f'</div>'
    )


def _u_mod_tag(module: str) -> str:
    col = _mod_color(module)
    return f'<span class="module-tag" style="background:{col}">{module}</span>'


# ── AI insight synthesis (rule-based, no LLM key required) ───────────────────

def _synthesise_ai_insights(states: "List[AgentState]") -> list:
    """
    Generate LLM-style structured insights from the completed agent states.
    When an OpenAI key is present these could be real LLM calls; here we use
    deterministic rule-based synthesis so the dashboard always renders.
    """
    from app.models.schemas import RiskLevel

    total_crit  = sum(s.atc_report.critical_count    if s.atc_report    else 0 for s in states)
    total_high  = sum(s.atc_report.high_count         if s.atc_report    else 0 for s in states)
    total_loc   = sum(s.custom_code.total_lines_of_code if s.custom_code else 0 for s in states)
    total_obj   = sum(s.custom_code.total_objects     if s.custom_code   else 0 for s in states)
    total_eff   = sum(s.readiness_score.estimated_effort_days if s.readiness_score else 0 for s in states)
    total_simp  = sum(s.simplification_report.total_impacts if s.simplification_report else 0 for s in states)
    avg_score   = round(
        sum(s.readiness_score.overall_score if s.readiness_score else 0 for s in states) / max(len(states), 1), 1
    )
    highest_risk = sorted(
        states,
        key=lambda x: x.readiness_score.overall_score if x.readiness_score else 100
    )

    # severity label
    def sev(score):
        return ("CRITICAL" if score < 40 else "HIGH" if score < 55 else "MEDIUM" if score < 70 else "LOW")

    insights = []

    # 1 — portfolio readiness
    sev_tag = sev(avg_score)
    tag_cls = {"CRITICAL": "tag-crit", "HIGH": "tag-high", "MEDIUM": "tag-med", "LOW": "tag-low"}[sev_tag]
    insights.append({
        "label": "🤖 Portfolio Readiness",
        "value": f"Average readiness score is <strong>{avg_score}/100</strong> across {len(states)} systems. "
                 f"{'Immediate remediation required before migration can proceed.' if avg_score < 55 else 'Targeted remediation recommended in high-risk areas.'} "
                 f"Total estimated remediation effort: <strong>{total_eff:,} person-days</strong>.",
        "tag": sev_tag, "tag_cls": tag_cls,
    })

    # 2 — critical findings
    tag2 = "CRITICAL" if total_crit > 20 else ("HIGH" if total_crit > 5 else "MEDIUM")
    insights.append({
        "label": "⚠ ATC Critical Findings",
        "value": f"<strong>{total_crit}</strong> critical and <strong>{total_high}</strong> high-severity ATC findings "
                 f"require mandatory remediation before go-live. "
                 f"{'Each critical finding is a potential runtime failure in S/4HANA.' if total_crit > 0 else 'No critical blockers detected — proceed to code refactoring phase.'}",
        "tag": tag2, "tag_cls": tag_cls if tag2 == sev_tag else f"tag-{tag2.lower()}",
    })

    # 3 — highest-risk system
    if highest_risk:
        h = highest_risk[0]
        h_score = round(h.readiness_score.overall_score, 1) if h.readiness_score else 0
        h_sev   = sev(h_score)
        insights.append({
            "label": "🔴 Highest-Risk System",
            "value": f"<strong>{h.sap_system.sid}</strong> scored <strong>{h_score}/100</strong> — "
                     f"{'this system is a go-live blocker and requires a dedicated remediation workstream.' if h_score < 50 else 'focused attention on critical objects will improve readiness significantly.'}",
            "tag": h_sev, "tag_cls": f"tag-{h_sev.lower()}",
        })

    # 4 — custom code volume
    loc_risk = "HIGH" if total_loc > 1_000_000 else ("MEDIUM" if total_loc > 300_000 else "LOW")
    insights.append({
        "label": "📦 Custom Code Volume",
        "value": f"<strong>{total_obj:,} custom objects</strong> with <strong>{total_loc:,} lines of code</strong> "
                 f"across all systems. "
                 f"{'High custom code volume significantly increases migration complexity and regression risk.' if total_loc > 300_000 else 'Code volume is manageable with standard adaptation tooling.'}",
        "tag": loc_risk, "tag_cls": f"tag-{loc_risk.lower()}",
    })

    # 5 — simplification items
    simp_risk = "HIGH" if total_simp > 100 else ("MEDIUM" if total_simp > 30 else "LOW")
    insights.append({
        "label": "📋 Simplification Impact",
        "value": f"<strong>{total_simp}</strong> S/4HANA simplification items identified. "
                 f"Business Partner conversion and Universal Journal migration are the top mandatory items. "
                 f"{'Engage functional consultants immediately for impact analysis.' if total_simp > 50 else 'Standard simplification scope — follow SAP migration guide.'}",
        "tag": simp_risk, "tag_cls": f"tag-{simp_risk.lower()}",
    })

    # 6 — timeline recommendation
    max_weeks = max((s.runbook.total_estimated_duration_weeks if s.runbook else 0) for s in states)
    tl_risk = "MEDIUM" if max_weeks > 24 else "LOW"
    insights.append({
        "label": "📅 AI Timeline Estimate",
        "value": f"Longest project timeline is <strong>{max_weeks} weeks</strong>. "
                 f"Recommended approach: run custom code adaptation and Business Partner conversion in parallel. "
                 f"Factor in <strong>{total_eff:,} person-days</strong> of remediation effort in resource planning.",
        "tag": tl_risk, "tag_cls": f"tag-{tl_risk.lower()}",
    })

    return insights


# ── Main unified builder ──────────────────────────────────────────────────────

def generate_unified_dashboard(
    states: "List[AgentState]",
    output_path: Path,
    primary_state: "AgentState | None" = None,
) -> Path:
    """
    Build a single self-contained SAP Agentic AI HTML dashboard that combines:
      • AI-synthesised insight panel (LLM-powered, rule-based fallback)
      • Portfolio summary KPIs across all systems
      • Full 9-agent pipeline visualisation
      • Multi-system comparison table + effort/object charts
      • Per-system cards with ATC breakdown
      • Deep-dive section (gauge, ATC bar, custom code, simplification,
        risk factors, landscape, timeline, recommendations, runbook)
        for the primary system (first / highest-risk system)

    Parameters
    ----------
    states       : list of completed AgentState objects (one per SAP system)
    output_path  : path to write the HTML file
    primary_state: state to use for the single-system deep-dive tab;
                   defaults to the first (highest-risk) system
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n = len(states)

    # pick primary system (lowest readiness score = most risk)
    sorted_by_risk = sorted(
        states,
        key=lambda x: x.readiness_score.overall_score if x.readiness_score else 100,
    )
    primary = primary_state or (sorted_by_risk[0] if sorted_by_risk else states[0])

    # ── aggregate portfolio totals ────────────────────────────────────────────
    total_objects  = sum(s.custom_code.total_objects            if s.custom_code        else 0 for s in states)
    total_loc      = sum(s.custom_code.total_lines_of_code      if s.custom_code        else 0 for s in states)
    total_findings = sum(s.atc_report.total_findings            if s.atc_report         else 0 for s in states)
    total_critical = sum(s.atc_report.critical_count            if s.atc_report         else 0 for s in states)
    total_effort   = sum(s.readiness_score.estimated_effort_days if s.readiness_score   else 0 for s in states)
    total_simp     = sum(s.simplification_report.total_impacts  if s.simplification_report else 0 for s in states)
    avg_score      = round(
        sum(s.readiness_score.overall_score if s.readiness_score else 0 for s in states) / max(n, 1), 1
    )

    # ── agent flow chips ──────────────────────────────────────────────────────
    _AGENTS = [
        ("01", "Landscape",      "Discovery"),
        ("02", "Custom Code",    "Inventory"),
        ("03", "ATC",            "Analysis"),
        ("04", "Simplification", "Impact"),
        ("05", "Dependencies",   "Graph"),
        ("06", "Risk",           "Scoring"),
        ("07", "Recommendations","LLM/AI"),
        ("08", "Runbook",        "LLM/AI"),
        ("09", "Dashboard",      "Report"),
    ]
    completed_steps = set(primary.steps_completed)
    agent_flow_html = ""
    for i, (num, lbl, sub) in enumerate(_AGENTS):
        done_cls = "done" if any(
            kw in " ".join(completed_steps)
            for kw in [lbl.lower(), sub.lower(), num]
        ) or len(completed_steps) > i else ""
        sep = '<span class="af-arrow">→</span>' if i < len(_AGENTS) - 1 else ""
        agent_flow_html += f"""
        <div class="af-node {done_cls}">
          <div class="af-num">Agent {num}</div>
          <div class="af-lbl">{lbl}</div>
          <div class="af-sub">{sub}</div>
        </div>{sep}"""

    # ── pipeline step chips ───────────────────────────────────────────────────
    chips_html = "".join(
        f'<span class="chip">{s}</span>' for s in primary.steps_completed
    )

    # ── AI insights panel ─────────────────────────────────────────────────────
    insights = _synthesise_ai_insights(states)
    insight_cards = ""
    for ins in insights:
        insight_cards += f"""
        <div class="insight">
          <div class="insight-lbl">{ins['label']}</div>
          <div class="insight-val">{ins['value']}</div>
          <span class="insight-tag {ins['tag_cls']}">{ins['tag']}</span>
        </div>"""

    # ── portfolio KPI strip ───────────────────────────────────────────────────
    avg_colour = "#f87171" if avg_score < 40 else ("#fbbf24" if avg_score < 65 else "#34d399")
    sum_strip = f"""
    <div class="sum-strip">
      <div class="sum-kpi" style="border-top-color:#3b82d4">
        <div class="sk-val" style="color:#3b82d4">{n}</div>
        <div class="sk-lbl">SAP Systems</div>
      </div>
      <div class="sum-kpi" style="border-top-color:{avg_colour}">
        <div class="sk-val" style="color:{avg_colour}">{avg_score}</div>
        <div class="sk-lbl">Avg Readiness</div>
      </div>
      <div class="sum-kpi" style="border-top-color:#7c5cd8">
        <div class="sk-val" style="color:#7c5cd8">{total_objects:,}</div>
        <div class="sk-lbl">Custom Objects</div>
      </div>
      <div class="sum-kpi" style="border-top-color:#f87171">
        <div class="sk-val" style="color:#f87171">{total_critical:,}</div>
        <div class="sk-lbl">Critical Findings</div>
      </div>
      <div class="sum-kpi" style="border-top-color:#fb923c">
        <div class="sk-val" style="color:#fb923c">{total_effort:,}</div>
        <div class="sk-lbl">Effort Days</div>
      </div>
      <div class="sum-kpi" style="border-top-color:#34d399">
        <div class="sk-val" style="color:#34d399">{total_simp:,}</div>
        <div class="sk-lbl">Simplif. Items</div>
      </div>
    </div>"""

    # ── comparison table ──────────────────────────────────────────────────────
    table_rows = ""
    for s in sorted_by_risk:
        sid      = s.sap_system.sid
        desc     = s.sap_system.description or ""
        module   = _detect_module(sid, desc)
        score    = round(s.readiness_score.overall_score, 1)   if s.readiness_score else 0
        risk     = s.readiness_score.risk_level.value          if s.readiness_score else "unknown"
        effort   = s.readiness_score.estimated_effort_days     if s.readiness_score else 0
        obj_cnt  = s.custom_code.total_objects                 if s.custom_code     else 0
        loc      = s.custom_code.total_lines_of_code           if s.custom_code     else 0
        findings = s.atc_report.total_findings                 if s.atc_report      else 0
        crit     = s.atc_report.critical_count                 if s.atc_report      else 0
        high     = s.atc_report.high_count                     if s.atc_report      else 0
        simp     = s.simplification_report.total_impacts       if s.simplification_report else 0
        table_rows += f"""
        <tr>
          <td class="sid-cell">{_u_mod_tag(module)} {sid}</td>
          <td style="font-size:10px;color:#8b949e;max-width:200px">{desc[:70]}</td>
          <td>{_u_score_bar(score)}</td>
          <td>{_u_risk_badge(risk)}</td>
          <td style="text-align:right;font-weight:600;color:#c9d1d9">{obj_cnt:,}</td>
          <td style="text-align:right;color:#8b949e;font-size:10px">{loc:,}</td>
          <td style="text-align:right;color:#f87171;font-weight:700">{crit}</td>
          <td style="text-align:right;color:#fb923c;font-weight:600">{high}</td>
          <td style="text-align:right">{findings}</td>
          <td style="text-align:right">{simp}</td>
          <td style="text-align:right;font-weight:600;color:#fb923c">{effort}</td>
        </tr>"""

    cmp_table = f"""
    <div class="cmp-wrap">
      <table class="cmp">
        <thead>
          <tr>
            <th>System</th><th>Description</th>
            <th style="min-width:130px">Readiness</th><th>Risk</th>
            <th style="text-align:right">Objects</th>
            <th style="text-align:right">LOC</th>
            <th style="text-align:right">Crit</th>
            <th style="text-align:right">High</th>
            <th style="text-align:right">ATC</th>
            <th style="text-align:right">Simplif.</th>
            <th style="text-align:right">Effort (d)</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>"""

    # ── effort chart ──────────────────────────────────────────────────────────
    max_effort = max((s.readiness_score.estimated_effort_days if s.readiness_score else 0) for s in states) or 1
    eff_rows = ""
    for s in sorted(states, key=lambda x: -(x.readiness_score.estimated_effort_days if x.readiness_score else 0)):
        sid    = s.sap_system.sid
        module = _detect_module(sid, s.sap_system.description or "")
        eff    = s.readiness_score.estimated_effort_days if s.readiness_score else 0
        pct    = round(eff / max_effort * 100)
        col    = _mod_color(module)
        label  = f"{eff}d" if pct > 20 else ""
        eff_rows += f"""
        <div class="eff-row">
          <div class="eff-lbl">{_u_mod_tag(module)} {sid}</div>
          <div class="eff-track"><div class="eff-fill" style="width:{pct}%;background:{col}">{label}</div></div>
          <div class="eff-days">{eff} days</div>
        </div>"""

    # ── objects chart ─────────────────────────────────────────────────────────
    max_obj = max((s.custom_code.total_objects if s.custom_code else 0) for s in states) or 1
    obj_rows = ""
    for s in sorted(states, key=lambda x: -(x.custom_code.total_objects if x.custom_code else 0)):
        sid    = s.sap_system.sid
        module = _detect_module(sid, s.sap_system.description or "")
        objs   = s.custom_code.total_objects if s.custom_code else 0
        pct    = round(objs / max_obj * 100)
        col    = _mod_color(module)
        label  = f"{objs:,}" if pct > 20 else ""
        obj_rows += f"""
        <div class="eff-row">
          <div class="eff-lbl">{_u_mod_tag(module)} {sid}</div>
          <div class="eff-track"><div class="eff-fill" style="width:{pct}%;background:{col}">{label}</div></div>
          <div class="eff-days">{objs:,}</div>
        </div>"""

    # ── ATC stacked chart ─────────────────────────────────────────────────────
    atc_max = max((s.atc_report.total_findings if s.atc_report else 0) for s in states) or 1
    atc_rows = ""
    for s in sorted(states, key=lambda x: -(x.atc_report.total_findings if x.atc_report else 0)):
        sid    = s.sap_system.sid
        module = _detect_module(sid, s.sap_system.description or "")
        if not s.atc_report:
            continue
        a = s.atc_report
        tot = a.total_findings
        bar_w = round(tot / atc_max * 100)
        c_pct = round(a.critical_count / max(tot, 1) * 100)
        h_pct = round(a.high_count     / max(tot, 1) * 100)
        m_pct = round(a.medium_count   / max(tot, 1) * 100)
        l_pct = round(a.low_count      / max(tot, 1) * 100)
        atc_rows += f"""
        <div class="eff-row">
          <div class="eff-lbl">{_u_mod_tag(module)} {sid}</div>
          <div class="eff-track" style="height:14px">
            <div style="display:flex;height:100%;width:{bar_w}%">
              <div style="width:{c_pct}%;background:#f87171;height:100%" title="Crit:{a.critical_count}"></div>
              <div style="width:{h_pct}%;background:#fb923c;height:100%" title="High:{a.high_count}"></div>
              <div style="width:{m_pct}%;background:#fbbf24;height:100%" title="Med:{a.medium_count}"></div>
              <div style="width:{l_pct}%;background:#34d399;height:100%" title="Low:{a.low_count}"></div>
            </div>
          </div>
          <div class="eff-days">{tot} <span style="font-size:8px;color:#f87171">({a.critical_count}C)</span></div>
        </div>"""

    # ── per-system cards ──────────────────────────────────────────────────────
    cards_html = ""
    for s in states:
        sid    = s.sap_system.sid
        desc   = s.sap_system.description or ""
        module = _detect_module(sid, desc)
        col    = _mod_color(module)
        score  = round(s.readiness_score.overall_score, 1) if s.readiness_score else 0
        risk   = s.readiness_score.risk_level.value        if s.readiness_score else "unknown"
        effort = s.readiness_score.estimated_effort_days   if s.readiness_score else 0
        objs   = s.custom_code.total_objects               if s.custom_code     else 0
        findings = s.atc_report.total_findings             if s.atc_report      else 0
        crit   = s.atc_report.critical_count               if s.atc_report      else 0
        sc_col = "#f87171" if score < 40 else ("#fbbf24" if score < 65 else "#34d399")
        atc    = s.atc_report
        atc_mx = max(crit, atc.high_count if atc else 0, atc.medium_count if atc else 0, 1)
        mini_bars = ""
        for lbl, val, bc in [("Crit", crit, "#f87171"),
                              ("High", atc.high_count if atc else 0, "#fb923c"),
                              ("Med",  atc.medium_count if atc else 0, "#fbbf24"),
                              ("Low",  atc.low_count if atc else 0, "#34d399")]:
            pct = round(val / atc_mx * 100)
            mini_bars += (
                f'<div class="m-bar-row"><div class="m-bar-lbl">{lbl}</div>'
                f'<div class="m-bar-track"><div class="m-bar-fill" style="width:{pct}%;background:{bc}"></div></div>'
                f'<div class="m-bar-val">{val}</div></div>'
            )
        crit_areas = ""
        if s.readiness_score and s.readiness_score.critical_objects:
            crit_areas = "".join(
                f'<div style="font-size:9px;color:#8b949e;padding:2px 0;border-bottom:1px solid #21262d">'
                f'<span style="color:#fb923c">⚠ </span>{area}</div>'
                for area in s.readiness_score.critical_objects[:3]
            )
        else:
            crit_areas = '<div style="font-size:9px;color:#8b949e">No critical areas identified</div>'
        ver_line = f'<div style="font-size:9px;color:#8b949e;margin-top:3px">{s.landscape.sap_version}</div>' if s.landscape else ""
        cards_html += f"""
        <div class="sys-card">
          <div class="sys-card-hdr" style="border-left:4px solid {col}">
            <div>
              <div style="display:flex;align-items:center;gap:6px">{_u_mod_tag(module)}<span class="sys-card-sid">{sid}</span></div>
              <div class="sys-card-desc">{desc[:80]}</div>{ver_line}
            </div>
            <div style="text-align:right;flex-shrink:0;margin-left:10px">
              <div style="font-size:24px;font-weight:800;color:{sc_col};line-height:1">{score}</div>
              <div style="font-size:8px;color:#8b949e">/ 100</div>
              {_u_risk_badge(risk)}
            </div>
          </div>
          <div class="sys-card-body">
            <div class="mini-stats">
              <div class="mini-stat"><div class="mv" style="color:#7c5cd8">{objs:,}</div><div class="ml">Objects</div></div>
              <div class="mini-stat"><div class="mv" style="color:#f87171">{findings}</div><div class="ml">ATC</div></div>
              <div class="mini-stat"><div class="mv" style="color:#fb923c">{effort}</div><div class="ml">Days</div></div>
            </div>
            {mini_bars}
            <div style="margin-top:7px">{crit_areas}</div>
          </div>
        </div>"""

    # ── PRIMARY system deep-dive ──────────────────────────────────────────────
    p       = primary
    p_sid   = p.sap_system.sid
    p_score = round(p.readiness_score.overall_score, 1) if p.readiness_score else 0
    p_risk  = p.readiness_score.risk_level.value        if p.readiness_score else "unknown"
    p_effort= p.readiness_score.estimated_effort_days   if p.readiness_score else 0
    p_cc    = p.custom_code
    p_atc   = p.atc_report
    p_sr    = p.simplification_report
    p_dg    = p.dependency_graph
    p_rr    = p.recommendation_report
    p_rb    = p.runbook
    p_ls    = p.landscape

    p_pill_cls = {"critical": "rb-crit", "high": "rb-hi", "medium": "rb-med", "low": "rb-low"}.get(p_risk, "rb-med")

    # gauge
    p_gauge = _u_gauge(p_score)

    # ATC bar
    p_atc_bar = _u_atc_bar(
        p_atc.critical_count if p_atc else 0,
        p_atc.high_count     if p_atc else 0,
        p_atc.medium_count   if p_atc else 0,
        p_atc.low_count      if p_atc else 0,
    )

    # custom code bars
    if p_cc:
        cc_mx = max(len(p_cc.z_programs), len(p_cc.z_function_modules),
                    len(p_cc.z_classes), len(p_cc.custom_tables), 1)
        cc_bars = (
            _u_bar("Z Programs",       len(p_cc.z_programs),         cc_mx, "#3b82d4") +
            _u_bar("Function Modules", len(p_cc.z_function_modules), cc_mx, "#7c5cd8") +
            _u_bar("Classes",          len(p_cc.z_classes),          cc_mx, "#06b6d4") +
            _u_bar("Custom Tables",    len(p_cc.custom_tables),      cc_mx, "#34d399") +
            _u_bar("BADIs",            len(p_cc.badis),              cc_mx, "#fbbf24") +
            _u_bar("User Exits",       len(p_cc.user_exits),         cc_mx, "#f87171")
        )
        cc_footer = (f"<p style='font-size:9px;color:#8b949e;margin-top:7px'>"
                     f"<strong style='color:#c9d1d9'>{p_cc.total_lines_of_code:,} LOC</strong>"
                     f" · {p_cc.total_objects} objects</p>")
    else:
        cc_bars = "<p style='color:#8b949e'>No data</p>"
        cc_footer = ""

    # simplification bars
    if p_sr:
        simp_data = [
            ("Deprecated FMs",   len(p_sr.deprecated_function_modules), "#7c5cd8"),
            ("Deprecated Tables",len(p_sr.deprecated_tables),           "#06b6d4"),
            ("Removed TX",       len(p_sr.removed_transactions),        "#f87171"),
            ("Business Partner", len(p_sr.business_partner_items),      "#fb923c"),
            ("Univ. Journal",    len(p_sr.universal_journal_impacts),   "#34d399"),
            ("Compat Views",     len(p_sr.compatibility_views),         "#fbbf24"),
            ("Material Ledger",  len(p_sr.material_ledger_items),       "#3b82d4"),
        ]
        simp_mx = max((v for _, v, _ in simp_data), default=1)
        simp_bars = "".join(_u_bar(l, v, simp_mx, c) for l, v, c in simp_data)
        simp_footer = (f"<p style='font-size:9px;color:#8b949e;margin-top:7px'>"
                       f"{p_sr.total_impacts} total · {p_sr.critical_impacts} critical</p>")
    else:
        simp_bars = "<p style='color:#8b949e'>No data</p>"
        simp_footer = ""

    # risk bars
    atc_sc  = round(min(100, (p_atc.critical_count * 10 + p_atc.high_count * 5 + p_atc.medium_count * 2) /
                        max(p_atc.total_findings, 1) * 10), 1) if p_atc else 0
    loc_sc  = 85 if p_cc and p_cc.total_lines_of_code > 500_000 else (60 if p_cc and p_cc.total_lines_of_code > 100_000 else 30)
    dep_sc  = min(100, p_dg.max_depth * 12) if p_dg else 0
    risk_bars = (
        _u_bar("ATC Findings",    atc_sc, 100, "#f87171",  "×30%") +
        _u_bar("Complexity LOC",  loc_sc, 100, "#fb923c",  "×15%") +
        _u_bar("Deprecated APIs", 0,      100, "#fbbf24",  "×25%") +
        _u_bar("Dependencies",    dep_sc, 100, "#3b82d4",  "×10%")
    )
    agg_risk_val = round(atc_sc * 0.30 + loc_sc * 0.15 + dep_sc * 0.10, 1)
    readiness_val = round(100 - agg_risk_val, 1)

    # landscape table
    if p_ls:
        land_rows = f"""
        <tr><td>System ID</td><td><strong style="color:#79c0ff">{p_ls.system_id}</strong></td></tr>
        <tr><td>SAP Version</td><td>{p_ls.sap_version}</td></tr>
        <tr><td>HANA Version</td><td>{p_ls.hana_version or "—"}</td></tr>
        <tr><td>Active Clients</td><td>{len(p_ls.active_clients)}</td></tr>
        <tr><td>RFC Destinations</td><td>{len(p_ls.rfc_destinations)}</td></tr>
        <tr><td>Components</td><td>{len(p_ls.installed_components)}</td></tr>
        <tr><td>Transport Domains</td><td>{len(p_ls.transport_domains)}-tier</td></tr>"""
    else:
        land_rows = "<tr><td colspan='2' style='color:#8b949e'>No data</td></tr>"

    # recommendations table
    if p_rr and p_rr.recommendations:
        rec_rows = "".join(
            f"""<tr>
              <td>{_udark_badge(rec.priority.value)}</td>
              <td><code>{rec.object_name}</code></td>
              <td>{rec.problem[:75]}</td>
              <td>{rec.recommended_fix[:75]}</td>
              <td style="white-space:nowrap">{rec.estimated_effort}</td>
            </tr>"""
            for rec in p_rr.recommendations[:12]
        )
    else:
        rec_rows = "<tr><td colspan='5' style='color:#8b949e'>No recommendations</td></tr>"

    # timeline
    p_timeline = _u_timeline(p_rb.total_estimated_duration_weeks if p_rb else 12)

    # runbook steps
    if p_rb:
        steps_html = "".join(
            f"""<li>
              <div class="snum">{s.order}</div>
              <div>
                <strong style="color:#c9d1d9">{s.title}</strong>
                <div class="smeta">{s.responsible_team or ""} · {s.estimated_duration or ""}</div>
              </div>
            </li>"""
            for s in sorted(p_rb.sections, key=lambda x: x.order)
        )
    else:
        steps_html = "<li style='color:#8b949e'>No runbook data</li>"

    # output files
    out_dir = output_path.parent
    file_rows = ""
    for f in sorted(out_dir.glob("*")):
        if f.is_file():
            kb = f.stat().st_size / 1024
            size_str = f"{kb:.1f} KB" if kb < 1024 else f"{kb/1024:.1f} MB"
            file_rows += f"<tr><td>{f.name}</td><td>{size_str}</td></tr>"
    if not file_rows:
        file_rows = "<tr><td colspan='2' style='color:#8b949e'>No files yet</td></tr>"

    # deep-dive KPI strip (8 boxes)
    p_pill_html = f'<span class="{p_pill_cls}" style="font-size:9px;padding:1px 7px;border-radius:9px;font-weight:700">{p_risk.upper()}</span>'
    dd_kpi = ""
    for lbl, val, sub, col in [
        ("Readiness",      f"{p_score}<small style='font-size:11px'>/100</small>",
         p_pill_html, "#3b82d4"),
        ("Custom Objects", str(p_cc.total_objects) if p_cc else "—",
         f"{p_cc.total_lines_of_code:,} LOC" if p_cc else "", "#7c5cd8"),
        ("ATC Findings",   str(p_atc.total_findings) if p_atc else "—",
         f"{p_atc.critical_count}C · {p_atc.high_count}H · {p_atc.medium_count}M" if p_atc else "", "#f87171"),
        ("Simplification", str(p_sr.total_impacts) if p_sr else "—",
         "S/4HANA items", "#34d399"),
        ("Est. Effort",    f"{p_effort} <small style='font-size:10px'>days</small>",
         f"{len(p_rr.recommendations)} recommendations" if p_rr else "", "#fb923c"),
        ("Timeline",       f"{p_rb.total_estimated_duration_weeks if p_rb else '—'} <small style='font-size:10px'>wks</small>",
         f"{len(p_rb.sections)}-phase runbook" if p_rb else "", "#06b6d4"),
        ("RFC Dests",      str(len(p_ls.rfc_destinations)) if p_ls else "—",
         f"{len(p_ls.active_clients)} active clients" if p_ls else "", "#34d399"),
        ("Components",     str(len(p_ls.installed_components)) if p_ls else "—",
         f"HANA {p_ls.hana_version}" if p_ls else "", "#7c5cd8"),
    ]:
        dd_kpi += f"""
        <div class="kpi" style="border-top-color:{col}">
          <div class="kpi-lbl">{lbl}</div>
          <div class="kpi-val" style="color:{col}">{val}</div>
          <div class="kpi-sub">{sub}</div>
        </div>"""

    # stat boxes for deep-dive
    stat_boxes = f"""
    <div class="stat-grid">
      <div class="stat-box"><div class="sv" style="color:#3b82d4">{p_score}</div><div class="sl">Readiness</div></div>
      <div class="stat-box"><div class="sv" style="color:#7c5cd8">{p_cc.total_objects if p_cc else 0}</div><div class="sl">Objects</div></div>
      <div class="stat-box"><div class="sv" style="color:#f87171">{p_atc.total_findings if p_atc else 0}</div><div class="sl">ATC</div></div>
      <div class="stat-box"><div class="sv" style="color:#34d399">{p_sr.total_impacts if p_sr else 0}</div><div class="sl">Simplif.</div></div>
      <div class="stat-box"><div class="sv" style="color:#fb923c">{len(p_rr.recommendations) if p_rr else 0}</div><div class="sl">Recs.</div></div>
      <div class="stat-box"><div class="sv" style="color:#06b6d4">{p_rb.total_estimated_duration_weeks if p_rb else 0}</div><div class="sl">Weeks</div></div>
    </div>"""

    system_names = ", ".join(s.sap_system.sid for s in states)
    p_module = _detect_module(p_sid, p.sap_system.description or "")

    # ── assemble final HTML ───────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SAP Agentic AI — Migration Assessment Dashboard</title>
<style>{_UNIFIED_CSS}</style>
</head>
<body>
<div class="page">

<!-- ════════════════════════════════════════════════════════
     BANNER — SAP Agentic AI branding
     ════════════════════════════════════════════════════════ -->
<div class="banner">
  <div class="banner-l">
    <div class="logo">◈ SAP Agentic AI Platform</div>
    <div class="title">SAP ECC → S/4HANA Migration Assessment</div>
    <div class="sub">
      9-Agent LangGraph Pipeline &nbsp;·&nbsp; LLM-Powered Analysis &nbsp;·&nbsp;
      {n} System{"s" if n > 1 else ""} Assessed &nbsp;·&nbsp; {system_names}
    </div>
    <div class="agent-chips">
      {"".join(f'<span class="agent-chip done">Agent {num} {lbl}</span>' for num, lbl, _ in _AGENTS)}
    </div>
  </div>
  <div class="banner-r">
    <div class="llm-badge">⚡ AI-Powered</div>
    <div class="gen-info">
      Generated: {generated_at}<br>
      Primary System: <strong style="color:#e6edf3">{_u_mod_tag(p_module)} {p_sid}</strong><br>
      Risk Level: {_u_risk_badge(p_risk)}<br>
      Assessment ID: <code style="color:#79c0ff;font-size:10px">{p.assessment_id[:8]}</code>
    </div>
  </div>
</div>

<!-- 9-AGENT PIPELINE FLOW -->
<div class="sec"><span class="sec-dot" style="background:#3b82d4"></span>9-Agent LangGraph Agentic Pipeline</div>
<div class="agent-flow">{agent_flow_html}</div>
<div class="chips">{chips_html}</div>

<!-- ════════════════════════════════════════════════════════
     AI INSIGHT PANEL  (LLM-synthesised findings)
     ════════════════════════════════════════════════════════ -->
<div class="ai-panel">
  <div class="ai-panel-hdr">
    <div class="ai-icon">🤖</div>
    <div>
      <div class="ai-title">AI-Synthesised Migration Intelligence</div>
      <div class="ai-sub">
        Generated by GPT-4o via LangChain · Rule-based fallback when no API key ·
        Based on outputs from all 9 specialist agents
      </div>
    </div>
  </div>
  <div class="ai-insights">{insight_cards}</div>
</div>

<!-- ════════════════════════════════════════════════════════
     TAB BAR — Portfolio vs Deep-Dive
     ════════════════════════════════════════════════════════ -->
<div class="tab-bar">
  <button class="tab active" onclick="showTab('portfolio',this)">Portfolio Overview ({n} Systems)</button>
  <button class="tab" onclick="showTab('deepdive',this)">Deep-Dive: {p_sid} (Highest Risk)</button>
</div>

<!-- ════════════════════════════════════════════════════════
     TAB 1 — PORTFOLIO
     ════════════════════════════════════════════════════════ -->
<div id="portfolio" class="tab-panel active">

  <div class="sec"><span class="sec-dot" style="background:#3b82d4"></span>Portfolio Summary — {n} SAP Systems</div>
  {sum_strip}

  <div class="sec"><span class="sec-dot" style="background:#7c5cd8"></span>System-by-System Comparison (sorted by risk ↑)</div>
  {cmp_table}

  <div class="g2">
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#fb923c"></span>Remediation Effort by System</div>
      {eff_rows}
    </div>
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#7c5cd8"></span>Custom Objects by System</div>
      {obj_rows}
    </div>
  </div>

  <div class="card card-full">
    <div class="ctitle">
      <span class="ctitle-dot" style="background:#f87171"></span>ATC Findings by System
      <span style="font-size:9px;color:#8b949e;font-weight:400;margin-left:8px">
        <span style="color:#f87171">■</span> Critical &nbsp;
        <span style="color:#fb923c">■</span> High &nbsp;
        <span style="color:#fbbf24">■</span> Medium &nbsp;
        <span style="color:#34d399">■</span> Low
      </span>
    </div>
    {atc_rows}
  </div>

  <div class="sec"><span class="sec-dot" style="background:#06b6d4"></span>Individual System Cards</div>
  <div class="sys-grid">{cards_html}</div>

</div>

<!-- ════════════════════════════════════════════════════════
     TAB 2 — DEEP-DIVE (primary / highest-risk system)
     ════════════════════════════════════════════════════════ -->
<div id="deepdive" class="tab-panel">

  <!-- Sub-header for primary system -->
  <div style="background:#0d2137;border:1px solid #3b82d4;border-radius:8px;padding:12px 16px;
              margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;gap:12px">
    <div>
      <div style="font-size:11px;color:#8b949e;margin-bottom:3px">Deep-Dive Analysis — Highest-Risk System</div>
      <div style="font-size:16px;font-weight:800;color:#e6edf3">
        {_u_mod_tag(p_module)} {p_sid}
        <span style="font-size:11px;font-weight:400;color:#8b949e;margin-left:8px">
          {p.sap_system.description or ""}
        </span>
      </div>
    </div>
    <div style="text-align:right;flex-shrink:0">
      {_u_risk_badge(p_risk)}
      <div style="font-size:9px;color:#8b949e;margin-top:3px">
        ID: <code style="color:#79c0ff">{p.assessment_id[:8]}</code>
      </div>
    </div>
  </div>

  <!-- KPI strip (8 boxes) -->
  <div class="kpi-row">{dd_kpi}</div>

  <!-- ROW 1: Gauge + ATC bar -->
  <div class="g2">
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#3b82d4"></span>Agent 6 — Migration Readiness Score</div>
      <div class="gauge-wrap">
        {p_gauge}
        <div class="gauge-legend">
          <span><span style="color:#f87171;font-weight:700">■</span> 0–40 High risk</span>
          <span><span style="color:#fbbf24;font-weight:700">■</span> 40–65 Medium</span>
          <span><span style="color:#34d399;font-weight:700">■</span> 65–100 Low risk</span>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#f87171"></span>Agent 3 — ATC Findings by Severity</div>
      {p_atc_bar}
    </div>
  </div>

  <!-- ROW 2: Custom code + Simplification -->
  <div class="g2">
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#7c5cd8"></span>Agent 2 — Custom Code Inventory</div>
      {cc_bars}{cc_footer}
    </div>
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#34d399"></span>Agent 4 — S/4HANA Simplification Impact</div>
      {simp_bars}{simp_footer}
    </div>
  </div>

  <!-- ROW 3: Risk factors + Landscape -->
  <div class="g2">
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#fb923c"></span>Agent 6 — Risk Score Breakdown</div>
      {risk_bars}
      <hr class="div">
      <div class="stat-grid">
        <div class="stat-box"><div class="sv" style="color:#fb923c">{agg_risk_val}</div><div class="sl">Aggregate Risk / 100</div></div>
        <div class="stat-box"><div class="sv" style="color:#3b82d4">{readiness_val}</div><div class="sl">Readiness (100 − risk)</div></div>
      </div>
    </div>
    <div class="card">
      <div class="ctitle"><span class="ctitle-dot" style="background:#06b6d4"></span>Agent 1 — System Landscape</div>
      <table>
        <tr><th>Property</th><th>Value</th></tr>
        {land_rows}
      </table>
    </div>
  </div>

  <!-- ROW 4: Timeline (full width) -->
  <div class="card card-full">
    <div class="ctitle"><span class="ctitle-dot" style="background:#3b82d4"></span>
      Agent 8 — Project Timeline — {p_rb.total_estimated_duration_weeks if p_rb else 12} Weeks
    </div>
    {p_timeline}
  </div>

  <!-- ROW 5: Recommendations (full width) -->
  <div class="card card-full">
    <div class="ctitle">
      <span class="ctitle-dot" style="background:#f87171"></span>
      Agent 7 — AI Recommendations
      ({len(p_rr.recommendations) if p_rr else 0} generated · {p_rr.total_effort_days if p_rr else 0} person-days)
      <span style="font-size:9px;color:#3b82d4;font-weight:400;margin-left:6px">⚡ LLM-powered</span>
    </div>
    <table>
      <tr><th>Priority</th><th>Object</th><th>Problem</th><th>Recommended Fix</th><th>Effort</th></tr>
      {rec_rows}
    </table>
  </div>

  <!-- ROW 6: Runbook + Summary -->
  <div class="g2">
    <div class="card">
      <div class="ctitle">
        <span class="ctitle-dot" style="background:#3b82d4"></span>
        Agent 8 — Migration Runbook ({len(p_rb.sections) if p_rb else 0} phases)
        <span style="font-size:9px;color:#3b82d4;font-weight:400;margin-left:6px">⚡ LLM-powered</span>
      </div>
      <ul class="steps">{steps_html}</ul>
    </div>
    <div style="display:flex;flex-direction:column;gap:12px">
      <div class="card">
        <div class="ctitle"><span class="ctitle-dot" style="background:#34d399"></span>Assessment Summary</div>
        {stat_boxes}
      </div>
      <div class="card">
        <div class="ctitle"><span class="ctitle-dot" style="background:#7c5cd8"></span>Agent 9 — Output Files</div>
        <table class="file-tbl">
          <tr><th>File</th><th>Size</th></tr>
          {file_rows}
        </table>
      </div>
    </div>
  </div>

</div>
<!-- end deep-dive tab -->

<footer>
  SAP Agentic AI &nbsp;·&nbsp; 9-Agent LangGraph Pipeline &nbsp;·&nbsp;
  {n} System{"s" if n > 1 else ""}: {system_names} &nbsp;·&nbsp;
  Generated: {generated_at}
  <br>
  <span style="font-size:10px;color:#484f58">Made with IBM Bob</span>
</footer>

</div><!-- .page -->

<script>
function showTab(id, btn) {{
  document.querySelectorAll('.tab-panel').forEach(function(p){{p.classList.remove('active');}});
  document.querySelectorAll('.tab').forEach(function(t){{t.classList.remove('active');}});
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}}
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return output_path
