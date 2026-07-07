"""
Agent 5 – Dependency Analyzer
Builds a dependency graph using NetworkX and exports PNG + interactive HTML.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import networkx as nx

from app.models.schemas import AgentState, DependencyEdge, DependencyGraph
from app.services import get_logger
from config.settings import get_settings

log = get_logger(__name__)
settings = get_settings()

_OUTPUT_DIR = Path(settings.reports_output_dir)


def _build_edges_from_atc(state: AgentState) -> List[DependencyEdge]:
    """Derive implicit program→function module edges from ATC findings."""
    edges: List[DependencyEdge] = []
    if not state.atc_report:
        return edges
    seen: set = set()
    for f in state.atc_report.findings:
        # Check message for FM names used inside program
        for token in f.message.split():
            if token.startswith(("REUSE_", "WRITE_", "LIST_", "BDC_", "CONVERSION_")):
                key = (f.object_name, token)
                if key not in seen:
                    edges.append(DependencyEdge(source=f.object_name, target=token, edge_type="calls"))
                    seen.add(key)
    return edges


def _build_table_edges(state: AgentState) -> List[DependencyEdge]:
    """Programs → custom tables (heuristic from object names)."""
    edges: List[DependencyEdge] = []
    if not state.custom_code:
        return edges
    tables = [t.object_name for t in state.custom_code.custom_tables]
    for prog in state.custom_code.z_programs[:10]:  # Top 10 for clarity
        for tbl in tables[:3]:
            edges.append(DependencyEdge(source=prog.object_name, target=tbl, edge_type="uses_table"))
    return edges


def _export_graph(G: nx.DiGraph, assessment_id: str) -> tuple[str | None, str | None]:
    """Export graph to PNG and interactive Plotly HTML."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path: str | None = None
    html_path: str | None = None

    # PNG via matplotlib
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(16, 10))
        pos = nx.spring_layout(G, seed=42, k=2.5)
        colors = []
        for node in G.nodes():
            if node.startswith("Z") or node.startswith("Y"):
                colors.append("#3b82d4")
            else:
                colors.append("#7c5cd8")
        nx.draw_networkx(G, pos, ax=ax, node_color=colors, node_size=600,
                         font_size=6, arrows=True, edge_color="#e5e7eb",
                         with_labels=True)
        ax.set_title(f"SAP Object Dependency Graph – {assessment_id}", fontsize=12)
        ax.axis("off")
        png_path = str(_OUTPUT_DIR / f"dependency_graph_{assessment_id}.png")
        fig.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        log.info("Dependency PNG exported", path=png_path)
    except Exception as exc:
        log.warning("PNG export failed", error=str(exc))

    # Interactive HTML via Plotly
    try:
        import plotly.graph_objects as go

        pos = nx.spring_layout(G, seed=42, k=2.5)
        edge_x, edge_y = [], []
        for src, tgt in G.edges():
            x0, y0 = pos[src]
            x1, y1 = pos[tgt]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

        node_x = [pos[n][0] for n in G.nodes()]
        node_y = [pos[n][1] for n in G.nodes()]
        node_labels = list(G.nodes())

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
                                  line=dict(width=1, color="#aaa"), hoverinfo="none"))
        fig.add_trace(go.Scatter(x=node_x, y=node_y, mode="markers+text",
                                  text=node_labels, textposition="top center",
                                  marker=dict(size=10, color="#3b82d4"),
                                  hovertext=node_labels))
        fig.update_layout(title=f"SAP Dependency Graph – {assessment_id}",
                          showlegend=False, xaxis=dict(showgrid=False, zeroline=False),
                          yaxis=dict(showgrid=False, zeroline=False),
                          paper_bgcolor="#ffffff", plot_bgcolor="#f7f8fa")
        html_path = str(_OUTPUT_DIR / f"dependency_graph_{assessment_id}.html")
        fig.write_html(html_path)
        log.info("Dependency HTML exported", path=html_path)
    except Exception as exc:
        log.warning("HTML export failed", error=str(exc))

    return png_path, html_path


def run_dependency_analysis(state: AgentState) -> AgentState:
    """LangGraph node: build and export the dependency graph."""
    log.info("Agent 5 – Dependency Analysis started", assessment_id=state.assessment_id)
    try:
        G = nx.DiGraph()

        nodes: List[Dict[str, Any]] = []
        if state.custom_code:
            for prog in state.custom_code.z_programs:
                G.add_node(prog.object_name, type="program")
                nodes.append({"id": prog.object_name, "type": "program"})
            for fm in state.custom_code.z_function_modules:
                G.add_node(fm.object_name, type="function_module")
                nodes.append({"id": fm.object_name, "type": "function_module"})
            for tbl in state.custom_code.custom_tables:
                G.add_node(tbl.object_name, type="table")
                nodes.append({"id": tbl.object_name, "type": "table"})

        all_edges = _build_edges_from_atc(state) + _build_table_edges(state)
        for edge in all_edges:
            G.add_edge(edge.source, edge.target, type=edge.edge_type)

        max_depth = nx.dag_longest_path_length(G) if nx.is_directed_acyclic_graph(G) else 0
        png_path, html_path = _export_graph(G, state.assessment_id)

        state.dependency_graph = DependencyGraph(
            nodes=nodes,
            edges=all_edges,
            graph_png_path=png_path,
            graph_html_path=html_path,
            max_depth=max_depth,
            generated_at=datetime.utcnow(),
        )

        state.steps_completed.append("dependency_analysis")
        state.current_step = "risk_assessment"
        log.info("Agent 5 – completed",
                 nodes=len(G.nodes()),
                 edges=len(G.edges()),
                 max_depth=max_depth)

    except Exception as exc:
        log.error("Agent 5 – failed", error=str(exc))
        state.error_messages.append(f"Dependency Analysis: {exc}")

    return state
