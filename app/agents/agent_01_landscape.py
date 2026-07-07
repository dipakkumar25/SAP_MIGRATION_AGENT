"""
Agent 1 – Landscape Discovery
Collects SAP system metadata via RFC.
"""
from __future__ import annotations

from datetime import datetime

from app.models.schemas import AgentState, LandscapeInventory
from app.services import get_logger, get_rfc_client

log = get_logger(__name__)


def run_landscape_discovery(state: AgentState) -> AgentState:
    """LangGraph node: discover SAP landscape."""
    log.info("Agent 1 – Landscape Discovery started", assessment_id=state.assessment_id)
    try:
        with get_rfc_client() as rfc:
            sys_info = rfc.call("RFC_SYSTEM_INFO")["RFCSI_EXPORT"]
            servers  = rfc.call("TH_SERVER_LIST").get("LIST", [])
            clients  = rfc.call("SUSR_GET_ADMIN_USER_LOGIN_INFO").get("CLIENTS", [])
            addons   = rfc.call("DELIVERY_GET_PACKAGES").get("PACKS", [])
            rfc_dest = rfc.call("RFC_GET_LOCAL_DESTINATIONS").get("DESTINATIONS", [])
            db_info  = rfc.call("DB6_GET_DB_SYSTEM_INFO")
            tms_info = rfc.call("TMS_MGR_GET_LANDSCAPE_INFO")
            transport_domains = [s.get("SYSNAM", "") for s in tms_info.get("SYSTEMS", [])]

        state.landscape = LandscapeInventory(
            system_id=sys_info.get("RFCSYSID", "UNKNOWN"),
            hostname=sys_info.get("RFCHOST", ""),
            sap_version=f"SAP ECC 6.0 EHP8 (Release {sys_info.get('RFCSAPRL', 'N/A')})",
            kernel_version=sys_info.get("RFCKERNRL", "N/A"),
            hana_version=f"{db_info.get('DB_SYSTEM','N/A')} {db_info.get('DB_RELEASE','N/A')}",
            installed_components=[
                {"component": a.get("COMPONENT", ""), "release": a.get("RELEASE", ""), "sp_level": a.get("SP_LEVEL", "")}
                for a in addons
            ],
            installed_addons=addons,
            active_clients=[
                {"client": c.get("MANDT", ""), "description": c.get("MTEXT", ""), "city": c.get("ORT01", "")}
                for c in clients
            ],
            transport_domains=transport_domains,
            rfc_destinations=[
                {"destination": d.get("RFCDEST", ""), "type": d.get("RFCTYPE", ""), "host": d.get("RFCHOST", "")}
                for d in rfc_dest
            ],
            collected_at=datetime.utcnow(),
        )

        state.steps_completed.append("landscape_discovery")
        state.current_step = "custom_code_discovery"
        log.info("Agent 1 – completed", system_id=state.landscape.system_id)

    except Exception as exc:
        log.error("Agent 1 – failed", error=str(exc))
        state.error_messages.append(f"Landscape Discovery: {exc}")

    return state
