"""
MCP Server for SAP Migration Assessment Agent.

Exposes all assessment capabilities as MCP tools that can be consumed
by any MCP-compatible AI client (Claude, Cursor, etc.).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from app.graph.workflow import run_assessment
from app.models.schemas import SAPSystem
from app.services import get_logger

log = get_logger(__name__)

server = Server("sap-migration-agent")


# ─────────────────────────────────────────────────────────────────────────────
# Tool registry
# ─────────────────────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="run_full_assessment",
            description="Run the complete SAP ECC to S/4HANA migration assessment pipeline.",
            inputSchema={
                "type": "object",
                "properties": {
                    "system_id":   {"type": "string", "description": "SAP System ID (SID), e.g. ECC"},
                    "host":        {"type": "string", "description": "SAP hostname or IP"},
                    "client":      {"type": "string", "description": "SAP client number"},
                    "description": {"type": "string", "description": "System description"},
                },
                "required": ["system_id", "host"],
            },
        ),
        Tool(
            name="get_landscape_inventory",
            description="Discover SAP system landscape metadata (version, components, clients).",
            inputSchema={
                "type": "object",
                "properties": {
                    "system_id": {"type": "string"},
                    "host":      {"type": "string"},
                },
                "required": ["system_id", "host"],
            },
        ),
        Tool(
            name="get_custom_programs",
            description="Retrieve all custom Z/Y programs, function modules, and classes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "system_id": {"type": "string"},
                    "host":      {"type": "string"},
                },
                "required": ["system_id", "host"],
            },
        ),
        Tool(
            name="run_atc",
            description="Execute SAP ATC checks and retrieve findings classified by severity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "system_id": {"type": "string"},
                    "host":      {"type": "string"},
                },
                "required": ["system_id", "host"],
            },
        ),
        Tool(
            name="get_simplification_items",
            description="Analyze system against SAP S/4HANA Simplification Database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "system_id": {"type": "string"},
                    "host":      {"type": "string"},
                },
                "required": ["system_id", "host"],
            },
        ),
        Tool(
            name="calculate_risk",
            description="Calculate migration readiness score and risk levels.",
            inputSchema={
                "type": "object",
                "properties": {
                    "assessment_id": {"type": "string", "description": "Existing assessment ID"},
                },
                "required": ["assessment_id"],
            },
        ),
        Tool(
            name="generate_runbook",
            description="Generate the full migration runbook (PDF, DOCX, Markdown).",
            inputSchema={
                "type": "object",
                "properties": {
                    "assessment_id": {"type": "string"},
                },
                "required": ["assessment_id"],
            },
        ),
        Tool(
            name="export_dashboard",
            description="Generate the executive dashboard (HTML, JSON).",
            inputSchema={
                "type": "object",
                "properties": {
                    "assessment_id": {"type": "string"},
                },
                "required": ["assessment_id"],
            },
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Tool execution
# ─────────────────────────────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "run_full_assessment":
            sap_system = SAPSystem(
                sid=arguments["system_id"],
                host=arguments["host"],
                client=arguments.get("client", "100"),
                description=arguments.get("description"),
            )
            state = run_assessment(sap_system)
            result = {
                "assessment_id": state.assessment_id,
                "overall_score": state.readiness_score.overall_score if state.readiness_score else None,
                "risk_level": state.readiness_score.risk_level.value if state.readiness_score else None,
                "steps_completed": state.steps_completed,
                "errors": state.error_messages,
                "runbook_markdown": state.runbook.markdown_path if state.runbook else None,
            }

        elif name == "get_landscape_inventory":
            from app.agents import run_landscape_discovery
            from app.models.schemas import AgentState
            sap_system = SAPSystem(sid=arguments["system_id"], host=arguments["host"])
            state = AgentState(assessment_id=str(uuid.uuid4()), sap_system=sap_system)
            state = run_landscape_discovery(state)
            result = state.landscape.model_dump() if state.landscape else {"error": "Discovery failed"}

        elif name == "get_custom_programs":
            from app.agents import run_custom_code_discovery
            from app.models.schemas import AgentState
            sap_system = SAPSystem(sid=arguments["system_id"], host=arguments["host"])
            state = AgentState(assessment_id=str(uuid.uuid4()), sap_system=sap_system)
            state = run_custom_code_discovery(state)
            result = {
                "total_objects": state.custom_code.total_objects,
                "total_loc": state.custom_code.total_lines_of_code,
                "z_programs": len(state.custom_code.z_programs),
                "function_modules": len(state.custom_code.z_function_modules),
                "classes": len(state.custom_code.z_classes),
            } if state.custom_code else {"error": "Discovery failed"}

        elif name == "run_atc":
            from app.agents import run_atc_assessment
            from app.models.schemas import AgentState
            sap_system = SAPSystem(sid=arguments["system_id"], host=arguments["host"])
            state = AgentState(assessment_id=str(uuid.uuid4()), sap_system=sap_system)
            state = run_atc_assessment(state)
            result = {
                "total_findings": state.atc_report.total_findings,
                "critical": state.atc_report.critical_count,
                "high": state.atc_report.high_count,
                "medium": state.atc_report.medium_count,
                "low": state.atc_report.low_count,
            } if state.atc_report else {"error": "ATC failed"}

        elif name in ("calculate_risk", "generate_runbook", "export_dashboard", "get_simplification_items"):
            result = {"message": f"Tool '{name}' requires a running assessment. Use run_full_assessment first.", "assessment_id": arguments.get("assessment_id")}

        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    except Exception as exc:
        log.error("MCP tool error", tool=name, error=str(exc))
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
