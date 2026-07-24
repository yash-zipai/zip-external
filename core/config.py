"""
ZipAI RAG — Application Configuration
Loads all settings from environment variables / .env file.
Uses Pydantic Settings for validation and type safety.
"""

from functools import lru_cache
from pydantic import AliasChoices, Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralised, validated application settings.
    All values are sourced from environment variables or a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_env: str = Field(default="development", description="Runtime environment")
    service_name: str = Field(default="zipai-rag", description="Service identifier for logs")
    log_level: str = Field(default="debug", description="Logging level: debug|info|warning|error")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(..., description="Async PostgreSQL DSN (asyncpg)")
    db_schema: str = Field(
        default="healthcare",
        description="PostgreSQL schema used by this microservice (default: rag)",
    )
    db_echo: bool = Field(
        default=False,
        description="Enable SQLAlchemy SQL query logging",
    )

    # ── AWS ───────────────────────────────────────────────────────────────────
    aws_region: str = Field(default="us-east-1")
    aws_access_key_id: str | None = Field(default=None)
    aws_secret_access_key: str | None = Field(default=None)
    aws_session_token: str | None = Field(default=None)

    # ── Bedrock Models ────────────────────────────────────────────────────────
    bedrock_embed_model_id: str = Field(
        default="amazon.titan-embed-text-v2:0",
        description="Bedrock embedding model ID",
    )
    bedrock_max_concurrency: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum concurrent Bedrock embedding requests",
    )
    bedrock_llm_model_id: str = Field(
        default="us.anthropic.claude-sonnet-4-6",
        description="Bedrock LLM model ID for answer generation",
    )
    bedrock_principle_llm_model_id: str | None = Field(
        default=None,
        description="Bedrock LLM model ID for planner/principal agent (optional fallback)",
    )

    # ── Planner Agent ─────────────────────────────────────────────────────
    planner_model_id: str = Field(
        default="us.anthropic.claude-sonnet-4-6",
        validation_alias=AliasChoices("bedrock_principle_llm_model_id", "planner_model_id"),
        description="Bedrock model ID for the planner agent (intent classification)",
    )
    planner_max_tokens: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Max output tokens for planner classification (keep low for speed)",
    )

    # ── Chunking ──────────────────────────────────────────────────────────────
    max_chunk_tokens: int = Field(default=512, ge=64, le=2048)
    min_chunk_tokens: int = Field(default=50, ge=10)
    overlap_tokens: int = Field(default=50, ge=0)

    # ── RAG Retrieval ─────────────────────────────────────────────────────────
    rag_top_k: int = Field(default=5, ge=1, le=20, description="Chunks retrieved per query")
    chat_history_window: int = Field(
        default=6, ge=2, le=20, description="Past messages included in context"
    )

    # ── S3 (Phase 2 — batch ingestion) ────────────────────────────────────────
    s3_bucket_name: str | None = Field(
        default=None,
        description="Default S3 bucket for PDF ingestion (can be overridden per-request).",
    )
    s3_prefix: str | None = Field(
        default=None,
        description="Optional default S3 prefix/folder (informational).",
    )

    # ── Fee Schedule Retrieval ─────────────────────────────────────────────────
    fee_top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum fee records returned per query (SQL + vector combined).",
    )
    fee_embed_on_ingest: bool = Field(
        default=True,
        description=(
            "Generate Titan V2 embeddings for fee records during ingestion. "
            "Set to False for SQL-only deployments to skip Bedrock embedding calls."
        ),
    )
    mlo_encryption_password: str = Field(
        default="ENCRYPT_PASSWORD",
        description="Secret key for pgp_sym_decrypt of MLO data",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns a cached singleton of Settings.
    Use FastAPI Depends(get_settings) or call directly in services.
    """
    return Settings()  # trigger reload to load updated .env model ID
