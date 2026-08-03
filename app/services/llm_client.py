"""
LLM factory: returns a configured LangChain chat model.

Supported backends (controlled by the ``LLM_BACKEND`` environment variable):

  - ``ica``     – IBM Consulting Advantage  (OpenAI-compatible REST at nextgen-beta.ica.ibm.com)
                  Uses langchain-openai with a custom base_url.  ← ACTIVE DEFAULT
  - ``openai``  – ChatOpenAI against api.openai.com
  - ``watsonx`` – ChatWatsonx via langchain-ibm (direct watsonx.ai, needs project_id)

IBM Consulting Advantage exposes an OpenAI-compatible endpoint, so no special SDK is needed.
Set the following in .env:
    LLM_BACKEND=ica
    ICA_API_KEY=k-d621b8f6f2ba45778983d93c6fd7936e
    ICA_BASE_URL=https://us-south.ml.cloud.ibm.com/ml/v1/text/chat   # or ICA gateway URL
    ICA_MODEL=meta-llama/llama-4-maverick-17b-instruct-fp8            # free-tier model
"""
from __future__ import annotations

from app.services.logger import get_logger
from config.settings import get_settings

log = get_logger(__name__)
settings = get_settings()

# Sentinel used by agent guards to detect a real key vs placeholder
_DUMMY_SENTINEL = "dummy"


def get_llm(temperature: float | None = None, model: str | None = None):
    """Return a configured LangChain BaseChatModel.

    The backend is chosen via ``LLM_BACKEND`` in .env:
      ``ica``      → IBM Consulting Advantage (OpenAI-compatible)
      ``openai``   → OpenAI directly
      ``watsonx``  → ibm-watsonx-ai SDK
    """
    backend = settings.llm_backend.lower()

    if backend == "ica":
        return _get_ica_llm(temperature=temperature, model=model)
    if backend == "watsonx":
        return _get_watsonx_llm(temperature=temperature, model_id=model)
    # Default: plain OpenAI
    return _get_openai_llm(temperature=temperature, model=model)


def is_llm_available() -> bool:
    """Return True when a real (non-placeholder) API key is configured."""
    backend = settings.llm_backend.lower()
    if backend == "ica":
        key = settings.ica_api_key.get_secret_value() if settings.ica_api_key else ""
        return bool(key) and _DUMMY_SENTINEL not in key
    if backend == "watsonx":
        key = settings.watsonx_api_key.get_secret_value() if settings.watsonx_api_key else ""
        return bool(key) and _DUMMY_SENTINEL not in key
    # openai
    key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    return bool(key) and _DUMMY_SENTINEL not in key


# ── IBM Consulting Advantage (OpenAI-compatible) ───────────────────────────────

def _get_ica_llm(temperature: float | None = None, model: str | None = None):
    """
    IBM Consulting Advantage exposes an OpenAI-compatible chat completions API.
    We use ChatOpenAI with a custom base_url and the ICA API key.
    """
    from langchain_openai import ChatOpenAI

    api_key = (
        settings.ica_api_key.get_secret_value()
        if settings.ica_api_key
        else "k-dummy-key"
    )
    resolved_model = model or settings.ica_model
    llm = ChatOpenAI(
        model=resolved_model,
        temperature=temperature if temperature is not None else settings.ica_temperature,
        max_tokens=settings.ica_max_tokens,
        api_key=api_key,
        base_url=settings.ica_base_url,
    )
    log.info("LLM initialised", backend="ica", model=resolved_model,
             base_url=settings.ica_base_url)
    return llm


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _get_openai_llm(temperature: float | None = None, model: str | None = None):
    from langchain_openai import ChatOpenAI

    api_key = (
        settings.openai_api_key.get_secret_value()
        if settings.openai_api_key
        else "sk-dummy-key-for-testing"
    )
    llm = ChatOpenAI(
        model=model or settings.openai_model,
        temperature=temperature if temperature is not None else settings.openai_temperature,
        max_tokens=settings.openai_max_tokens,
        api_key=api_key,
    )
    log.info("LLM initialised", backend="openai", model=llm.model_name)
    return llm


# ── IBM watsonx (direct SDK — needs project_id) ───────────────────────────────

def _get_watsonx_llm(temperature: float | None = None, model_id: str | None = None):
    from langchain_ibm import ChatWatsonx

    api_key = (
        settings.watsonx_api_key.get_secret_value()
        if settings.watsonx_api_key
        else None
    )
    resolved_model = model_id or settings.watsonx_model_id
    llm = ChatWatsonx(
        model_id=resolved_model,
        url=settings.watsonx_url,
        apikey=api_key,
        project_id=settings.watsonx_project_id,
        params={
            "temperature": temperature if temperature is not None else settings.watsonx_temperature,
            "max_new_tokens": settings.watsonx_max_new_tokens,
        },
    )
    log.info("LLM initialised", backend="watsonx", model=resolved_model)
    return llm
