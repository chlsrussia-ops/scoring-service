from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SCORING_",
        extra="ignore",
    )

    app_name: str = "scoring-service"
    env: str = "dev"
    log_level: str = "INFO"
    log_json: bool = True

    min_score: float = 0.0
    max_score: float = 100.0
    max_text_weight_per_field: float = 10.0
    max_collection_bonus: float = 8.0
    max_nested_bonus: float = 12.0
    numeric_multiplier: float = 0.10
    item_weight: float = 2.0
    collection_weight: float = 0.75
    nested_weight: float = 1.5
    true_flag_bonus: float = 2.0

    emit_metrics: bool = True
    emit_analytics: bool = True
    pretty_json_indent: int = 2
    fallback_on_error: bool = True

    reviewer_excellent_threshold: float = 80.0
    reviewer_approved_threshold: float = 50.0
    reviewer_manual_review_threshold: float = 20.0
    max_diagnostics: int = 20

    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)

    api_keys: str = "dev-key-1"
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    otel_enabled: bool = False
    otel_service_name: str = "scoring-service"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    db_echo: bool = False

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]
