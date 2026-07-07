"""
Agent 2 – Custom Code Discovery
Retrieves all Z/Y objects, enhancements, BADIs and user exits via RFC.
"""
from __future__ import annotations

from datetime import datetime

from app.models.schemas import AgentState, CustomCodeInventory, CustomObject, ObjectType
from app.services import get_logger, get_rfc_client

log = get_logger(__name__)


def _parse_date(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw, "%Y%m%d") if raw else None
    except ValueError:
        return None


def _to_custom_objects(records: list, obj_type: ObjectType, name_key: str) -> list[CustomObject]:
    result = []
    for r in records:
        result.append(CustomObject(
            object_name=r.get(name_key, "UNKNOWN"),
            object_type=obj_type,
            package=r.get("DEVCLASS"),
            owner=r.get("CNAM") or r.get("UNAM"),
            lines_of_code=int(r.get("LINES", 0)),
            last_changed_by=r.get("UNAM"),
            last_changed_date=_parse_date(r.get("UDAT", "")),
            transport_request=r.get("TRKORR"),
        ))
    return result


def run_custom_code_discovery(state: AgentState) -> AgentState:
    """LangGraph node: discover all custom Z/Y developments."""
    log.info("Agent 2 – Custom Code Discovery started", assessment_id=state.assessment_id)
    try:
        with get_rfc_client() as rfc:
            programs    = rfc.call("Z_GET_CUSTOM_PROGRAMS").get("PROGRAMS", [])
            fms         = rfc.call("Z_GET_FUNCTION_MODULES").get("FUNCTION_MODULES", [])
            classes     = rfc.call("Z_GET_CLASSES").get("CLASSES", [])
            tables      = rfc.call("Z_GET_CUSTOM_TABLES").get("TABLES", [])
            enhancements = rfc.call("Z_GET_ENHANCEMENTS").get("ENHANCEMENTS", [])

        z_programs = _to_custom_objects(programs, ObjectType.PROGRAM, "PROGNAME")
        z_fms      = _to_custom_objects(fms, ObjectType.FUNCTION_MODULE, "FUNCNAME")
        z_classes  = _to_custom_objects(classes, ObjectType.CLASS, "CLSNAME")
        z_tables   = _to_custom_objects(tables, ObjectType.TABLE, "TABNAME")

        badis = [CustomObject(
            object_name=e.get("ENHNAME", "UNKNOWN"),
            object_type=ObjectType.BADI,
            package=e.get("DEVCLASS"),
        ) for e in enhancements if e.get("TYPE") == "BADI"]

        user_exits = [CustomObject(
            object_name=e.get("ENHNAME", "UNKNOWN"),
            object_type=ObjectType.USER_EXIT,
            package=e.get("DEVCLASS"),
        ) for e in enhancements if e.get("TYPE") == "USER_EXIT"]

        all_objects = z_programs + z_fms + z_classes + z_tables + badis + user_exits
        total_loc = sum(o.lines_of_code for o in all_objects)

        state.custom_code = CustomCodeInventory(
            z_programs=z_programs,
            z_function_modules=z_fms,
            z_classes=z_classes,
            custom_tables=z_tables,
            badis=badis,
            user_exits=user_exits,
            total_objects=len(all_objects),
            total_lines_of_code=total_loc,
            collected_at=datetime.utcnow(),
        )

        state.steps_completed.append("custom_code_discovery")
        state.current_step = "atc_assessment"
        log.info("Agent 2 – completed",
                 total_objects=state.custom_code.total_objects,
                 total_loc=state.custom_code.total_lines_of_code)

    except Exception as exc:
        log.error("Agent 2 – failed", error=str(exc))
        state.error_messages.append(f"Custom Code Discovery: {exc}")

    return state
