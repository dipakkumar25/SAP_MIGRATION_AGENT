"""
Central application settings loaded from environment variables / .env file.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "SAP Migration Assessment Agent"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # ── API Security ─────────────────────────────────────────────────────────
    secret_key: SecretStr = Field(default="change-me-in-production-32-chars!!")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    api_key_header: str = "X-API-Key"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://sap_agent:sap_agent@localhost:5432/sap_migration"
    database_url_sync: str = "postgresql://sap_agent:sap_agent@localhost:5432/sap_migration"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "sap_migration_kb"

    # ── OpenAI ───────────────────────────────────────────────────────────────
    openai_api_key: Optional[SecretStr] = None
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.1
    openai_max_tokens: int = 4096

    # ── LangSmith ────────────────────────────────────────────────────────────
    langchain_tracing_v2: bool = False
    langchain_api_key: Optional[SecretStr] = None
    langchain_project: str = "sap-migration-agent"

    # ── SAP Connection ───────────────────────────────────────────────────────
    sap_host: str = "localhost"
    sap_sysnr: str = "00"
    sap_client: str = "100"
    sap_user: str = "RFC_USER"
    sap_password: Optional[SecretStr] = None
    sap_lang: str = "EN"
    sap_router: Optional[str] = None
    sap_use_mock: bool = True          # Use mock RFC when real SAP unavailable

    # ── SAP OData ────────────────────────────────────────────────────────────
    sap_odata_base_url: str = "http://localhost:8080/sap/opu/odata/sap"
    sap_odata_user: str = "odata_user"
    sap_odata_password: Optional[SecretStr] = None

    # ── Reports ──────────────────────────────────────────────────────────────
    reports_output_dir: str = "output/reports"
    templates_dir: str = "app/reports/templates"

    # ── Frontend ─────────────────────────────────────────────────────────────
    api_base_url: str = "http://localhost:8000"

    # ── LangGraph ────────────────────────────────────────────────────────────
    langgraph_checkpointer: str = "postgres"   # "memory" or "postgres"
    max_agent_retries: int = 3
    agent_timeout_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
