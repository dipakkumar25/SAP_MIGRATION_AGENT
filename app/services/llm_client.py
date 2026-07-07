"""
LLM factory: returns a configured LangChain ChatOpenAI instance.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.services.logger import get_logger
from config.settings import get_settings

log = get_logger(__name__)
settings = get_settings()


def get_llm(temperature: float | None = None, model: str | None = None) -> ChatOpenAI:
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
    log.info("LLM initialised", model=llm.model_name)
    return llm
