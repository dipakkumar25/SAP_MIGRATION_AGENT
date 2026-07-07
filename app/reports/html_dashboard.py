"""
Static HTML Dashboard Generator
================================
Builds a fully self-contained, zero-dependency HTML dashboard from an
AgentState object and writes it to disk.

Called automatically by run_sample.py after every pipeline run.
Output:  output/reports/dashboard_<assessment_id>.html
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

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
