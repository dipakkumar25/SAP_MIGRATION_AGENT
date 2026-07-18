"""
All FastAPI route handlers.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.agents import (
    run_atc_assessment,
    run_custom_code_discovery,
    run_dependency_analysis,
    run_landscape_discovery,
    run_recommendation_generation,
    run_risk_assessment,
    run_runbook_generation,
    run_simplification_analysis,
    run_dashboard_generation,
)
from app.agents.agent_09_dashboard import build_dashboard_data
from app.graph.workflow import run_assessment_async
from app.models.schemas import AgentState, MigrationStatus, SAPSystem
from app.services import get_logger
from config.settings import get_settings

router = APIRouter()
log = get_logger(__name__)
settings = get_settings()

# In-memory assessment store (replace with DB in production)
_assessments: Dict[str, AgentState] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class AssessmentRequest(BaseModel):
    system_id: str
    host: str
    sysnr: str = "00"
    client: str = "100"
    description: Optional[str] = None


class AssessmentResponse(BaseModel):
    assessment_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    assessment_id: str
    status: str
    current_step: str
    steps_completed: list
    overall_score: Optional[float] = None
    risk_level: Optional[str] = None
    errors: list = []
    dashboard_link: Optional[str] = None
    runbook_pdf_link: Optional[str] = None
    runbook_docx_link: Optional[str] = None
    runbook_markdown_link: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Health & Status
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health", tags=["System"])
async def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/status/{assessment_id}", response_model=StatusResponse, tags=["Assessment"])
async def get_status(assessment_id: str) -> StatusResponse:
    state = _assessments.get(assessment_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")

    # Resolve dashboard and runbook download links once the pipeline is done
    aid = assessment_id[:8]
    s = get_settings()
    out = Path(s.reports_output_dir)
    dash_html = out / f"dashboard_{aid}.html"

    return StatusResponse(
        assessment_id=assessment_id,
        status=state.status.value,
        current_step=state.current_step,
        steps_completed=state.steps_completed,
        overall_score=state.readiness_score.overall_score if state.readiness_score else None,
        risk_level=state.readiness_score.risk_level.value if state.readiness_score else None,
        errors=state.error_messages,
        dashboard_link=f"/api/v1/dashboard/{assessment_id}/html" if dash_html.exists() else None,
        runbook_pdf_link=f"/api/v1/report/{assessment_id}/pdf" if (out / f"runbook_{aid}.pdf").exists() else None,
        runbook_docx_link=f"/api/v1/report/{assessment_id}/docx" if (out / f"runbook_{aid}.docx").exists() else None,
        runbook_markdown_link=f"/api/v1/report/{assessment_id}/markdown" if (out / f"runbook_{aid}.md").exists() else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Full Assessment (async background)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/assess", response_model=AssessmentResponse, status_code=202, tags=["Assessment"])
async def start_assessment(req: AssessmentRequest, background_tasks: BackgroundTasks) -> AssessmentResponse:
    assessment_id = str(uuid.uuid4())
    sap_system = SAPSystem(
        sid=req.system_id, host=req.host,
        sysnr=req.sysnr, client=req.client,
        description=req.description,
    )
    initial_state = AgentState(
        assessment_id=assessment_id,
        sap_system=sap_system,
        status=MigrationStatus.IN_PROGRESS,
    )
    _assessments[assessment_id] = initial_state

    async def _run():
        try:
            final = await run_assessment_async(sap_system, assessment_id)
            final.status = MigrationStatus.COMPLETED
            _assessments[assessment_id] = final
        except Exception as exc:
            log.error("Assessment failed", assessment_id=assessment_id, error=str(exc))
            _assessments[assessment_id].status = MigrationStatus.FAILED
            _assessments[assessment_id].error_messages.append(str(exc))

    background_tasks.add_task(_run)
    log.info("Assessment queued", assessment_id=assessment_id, system=req.system_id)
    return AssessmentResponse(
        assessment_id=assessment_id,
        status="queued",
        message=f"Assessment started. Poll GET /api/v1/status/{assessment_id}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Individual agent endpoints
# ─────────────────────────────────────────────────────────────────────────────

def _get_fresh_state(req: AssessmentRequest) -> AgentState:
    return AgentState(
        assessment_id=str(uuid.uuid4()),
        sap_system=SAPSystem(sid=req.system_id, host=req.host,
                             sysnr=req.sysnr, client=req.client),
    )


@router.post("/inventory", tags=["Agents"])
async def get_inventory(req: AssessmentRequest) -> Dict[str, Any]:
    state = _get_fresh_state(req)
    state = run_landscape_discovery(state)
    if state.landscape:
        return state.landscape.model_dump()
    raise HTTPException(500, detail="Landscape discovery failed")


@router.post("/custom-code", tags=["Agents"])
async def get_custom_code(req: AssessmentRequest) -> Dict[str, Any]:
    state = _get_fresh_state(req)
    state = run_custom_code_discovery(state)
    if state.custom_code:
        return {
            "total_objects": state.custom_code.total_objects,
            "total_lines_of_code": state.custom_code.total_lines_of_code,
            "z_programs": [p.model_dump() for p in state.custom_code.z_programs],
            "z_function_modules": [f.model_dump() for f in state.custom_code.z_function_modules],
            "z_classes": [c.model_dump() for c in state.custom_code.z_classes],
            "custom_tables": [t.model_dump() for t in state.custom_code.custom_tables],
        }
    raise HTTPException(500, detail="Custom code discovery failed")


@router.post("/atc", tags=["Agents"])
async def run_atc(req: AssessmentRequest) -> Dict[str, Any]:
    state = _get_fresh_state(req)
    state = run_atc_assessment(state)
    if state.atc_report:
        return state.atc_report.model_dump()
    raise HTTPException(500, detail="ATC assessment failed")


@router.post("/dependencies", tags=["Agents"])
async def get_dependencies(req: AssessmentRequest) -> Dict[str, Any]:
    state = _get_fresh_state(req)
    state = run_custom_code_discovery(state)
    state = run_atc_assessment(state)
    state = run_dependency_analysis(state)
    if state.dependency_graph:
        return {
            "node_count": len(state.dependency_graph.nodes),
            "edge_count": len(state.dependency_graph.edges),
            "max_depth": state.dependency_graph.max_depth,
            "graph_html": state.dependency_graph.graph_html_path,
        }
    raise HTTPException(500, detail="Dependency analysis failed")


@router.post("/risk", tags=["Agents"])
async def assess_risk(req: AssessmentRequest) -> Dict[str, Any]:
    state = _get_fresh_state(req)
    state = run_custom_code_discovery(state)
    state = run_atc_assessment(state)
    state = run_simplification_analysis(state)
    state = run_dependency_analysis(state)
    state = run_risk_assessment(state)
    if state.readiness_score:
        return state.readiness_score.model_dump()
    raise HTTPException(500, detail="Risk assessment failed")


@router.post("/recommendations", tags=["Agents"])
async def get_recommendations(req: AssessmentRequest) -> Dict[str, Any]:
    state = _get_fresh_state(req)
    state = run_custom_code_discovery(state)
    state = run_atc_assessment(state)
    state = run_simplification_analysis(state)
    state = run_dependency_analysis(state)
    state = run_risk_assessment(state)
    state = run_recommendation_generation(state)
    if state.recommendation_report:
        return state.recommendation_report.model_dump()
    raise HTTPException(500, detail="Recommendation generation failed")


@router.post("/runbook", tags=["Agents"])
async def generate_runbook_endpoint(req: AssessmentRequest) -> Dict[str, Any]:
    state = _get_fresh_state(req)
    state = run_custom_code_discovery(state)
    state = run_atc_assessment(state)
    state = run_simplification_analysis(state)
    state = run_dependency_analysis(state)
    state = run_risk_assessment(state)
    state = run_runbook_generation(state)
    state = run_dashboard_generation(state)
    if state.runbook:
        aid = state.assessment_id[:8]
        s = get_settings()
        dash_html = Path(s.reports_output_dir) / f"dashboard_{aid}.html"
        return {
            "project_name": state.runbook.project_name,
            "sections": len(state.runbook.sections),
            "estimated_weeks": state.runbook.total_estimated_duration_weeks,
            "markdown_path": state.runbook.markdown_path,
            "pdf_path": state.runbook.pdf_path,
            "docx_path": state.runbook.docx_path,
            "dashboard_link": f"/api/v1/dashboard/{state.assessment_id}/html" if dash_html.exists() else None,
            "dashboard_json_link": f"/api/v1/dashboard/{state.assessment_id}",
        }
    raise HTTPException(500, detail="Runbook generation failed")


@router.get("/dashboard/{assessment_id}", tags=["Dashboard"])
async def get_dashboard(assessment_id: str) -> Dict[str, Any]:
    state = _assessments.get(assessment_id)
    if not state:
        raise HTTPException(404, detail="Assessment not found")
    return build_dashboard_data(state)


@router.get("/dashboard/{assessment_id}/html", tags=["Dashboard"])
async def get_dashboard_html(assessment_id: str):
    from config.settings import get_settings
    s = get_settings()
    html_path = Path(s.reports_output_dir) / f"dashboard_{assessment_id[:8]}.html"
    if not html_path.exists():
        raise HTTPException(404, detail="Dashboard HTML not yet generated")
    return FileResponse(str(html_path), media_type="text/html")


@router.get("/dashboard/unified", tags=["Dashboard"])
async def get_unified_dashboard():
    """
    Serve the unified SAP Agentic AI dashboard (all systems + deep-dive).
    Generated by run_sample.py or any multi-assessment pipeline run.
    """
    from config.settings import get_settings
    s = get_settings()
    html_path = Path(s.reports_output_dir) / "dashboard_unified_agentic_ai.html"
    if not html_path.exists():
        raise HTTPException(
            404,
            detail="Unified dashboard not yet generated. Run the assessment pipeline first.",
        )
    return FileResponse(str(html_path), media_type="text/html")


@router.get("/dashboard/unified/generate", tags=["Dashboard"])
async def generate_unified_dashboard_endpoint(background_tasks: BackgroundTasks):
    """
    Re-generate the unified SAP Agentic AI dashboard from all completed assessments
    currently held in the in-memory store.
    """
    from app.reports.html_dashboard import generate_unified_dashboard
    from config.settings import get_settings

    completed = [
        state for state in _assessments.values()
        if state.status.value == "completed"
    ]
    if not completed:
        raise HTTPException(
            400,
            detail="No completed assessments in store. Run /assess first.",
        )

    def _regen():
        s = get_settings()
        out = Path(s.reports_output_dir) / "dashboard_unified_agentic_ai.html"
        generate_unified_dashboard(completed, out)
        log.info("Unified Agentic AI dashboard regenerated", systems=len(completed), path=str(out))

    background_tasks.add_task(_regen)
    return {
        "status": "generating",
        "message": f"Regenerating unified dashboard from {len(completed)} completed assessment(s).",
        "link": "/api/v1/dashboard/unified",
    }


@router.get("/report/{assessment_id}/{file_type}", tags=["Reports"])
async def download_report(assessment_id: str, file_type: str):
    from config.settings import get_settings
    s = get_settings()
    output_dir = Path(s.reports_output_dir)
    file_map = {
        "pdf":      output_dir / f"runbook_{assessment_id[:8]}.pdf",
        "docx":     output_dir / f"runbook_{assessment_id[:8]}.docx",
        "markdown": output_dir / f"runbook_{assessment_id[:8]}.md",
    }
    path = file_map.get(file_type)
    if path is None:
        raise HTTPException(400, detail=f"Unknown file type: {file_type}")
    if not path.exists():
        raise HTTPException(404, detail="Report not yet generated")
    return FileResponse(str(path), filename=path.name)
