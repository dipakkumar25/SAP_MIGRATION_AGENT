"""
SAP RFC connection factory.
Returns a real pyrfc.Connection when SAP_USE_MOCK=false and pyrfc is available,
otherwise falls back to MockRFCClient.
"""
from __future__ import annotations

from typing import Any, Dict

from app.services.logger import get_logger
from app.services.mock_rfc import MockRFCClient
from config.settings import get_settings

log = get_logger(__name__)
settings = get_settings()


def get_rfc_client(**override_params: Any):
    """Return an RFC client (mock or real)."""
    params: Dict[str, Any] = {
        "ashost": settings.sap_host,
        "sysnr": settings.sap_sysnr,
        "client": settings.sap_client,
        "user": settings.sap_user,
        "passwd": settings.sap_password.get_secret_value() if settings.sap_password else "",
        "lang": settings.sap_lang,
    }
    if settings.sap_router:
        params["saprouter"] = settings.sap_router
    params.update(override_params)

    if settings.sap_use_mock:
        log.info("Using MockRFCClient (SAP_USE_MOCK=true)")
        return MockRFCClient(**params)

    try:
        import pyrfc  # type: ignore
        log.info("Using real pyrfc.Connection", host=settings.sap_host)
        return pyrfc.Connection(**params)
    except ImportError:
        log.warning("pyrfc not installed – falling back to MockRFCClient")
        return MockRFCClient(**params)
    except Exception as exc:
        log.error("RFC connection failed – falling back to MockRFCClient", error=str(exc))
        return MockRFCClient(**params)
