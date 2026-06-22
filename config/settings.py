from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings loaded from environment variables / .env file.
    All values can be overridden by setting the corresponding environment variable.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM Provider ─────────────────────────────────────────────────────────
    llm_provider: str = Field(default="openai")  # openai | anthropic

    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")

    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022")

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(default="sqlite:///./data/support_agent.db")

    # ── Vector Store ─────────────────────────────────────────────────────────
    chroma_persist_path: str = Field(default="./data/chroma_db")

    # ── Langfuse ─────────────────────────────────────────────────────────────
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")

    # ── FastAPI ───────────────────────────────────────────────────────────────
    app_name: str = Field(default="AI Customer Support Agent")
    app_version: str = Field(default="0.1.0")
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)
    secret_key: str = Field(default="change-me-in-production")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # ── Agent ─────────────────────────────────────────────────────────────────
    confidence_threshold: float = Field(default=0.75)
    max_retrieval_docs: int = Field(default=5)
    max_similar_cases: int = Field(default=3)
    high_value_refund_threshold: float = Field(default=500.0)

    # ── Airflow ───────────────────────────────────────────────────────────────
    airflow_home: str = Field(default="./orchestration/airflow")

    # ── AWS ───────────────────────────────────────────────────────────────────
    aws_region: str = Field(default="us-east-1")
    aws_access_key_id: str = Field(default="")
    aws_secret_access_key: str = Field(default="")
    s3_bucket_name: str = Field(default="")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def active_llm_model(self) -> str:
        """Returns the model name for the active LLM provider."""
        if self.llm_provider == "anthropic":
            return self.anthropic_model
        return self.openai_model


# Single shared instance — import this everywhere
settings = Settings()
