from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SCORING_",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────
    app_name: str = "scoring-service"
    env: str = "dev"
    log_level: str = "INFO"
    log_json: bool = True

    # ── Scoring engine ───────────────────────────────────────────────
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

    # ── API ──────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)
    max_request_body_bytes: int = 1_048_576

    api_keys: str = "dev-key-1"
    admin_api_key: str = "admin-secret-key"
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # ── Database ─────────────────────────────────────────────────────
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/scoring"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # ── Observability / Tracing ──────────────────────────────────────
    otel_enabled: bool = False
    otel_service_name: str = "scoring-service"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    # ── Idempotency ──────────────────────────────────────────────────
    enable_idempotency: bool = True
    idempotency_ttl_seconds: int = 86400
    dedup_window_seconds: int = 3600

    # ── Job Queue ────────────────────────────────────────────────────
    enable_jobs: bool = True
    job_max_attempts: int = 5
    job_backoff_base_seconds: float = 2.0
    job_backoff_max_seconds: float = 300.0
    job_backoff_jitter: bool = True
    job_stale_lock_timeout_seconds: int = 600
    job_lease_duration_seconds: int = 300
    job_poll_interval_seconds: float = 5.0
    job_batch_size: int = 10

    # ── Outbox ───────────────────────────────────────────────────────
    enable_outbox: bool = True
    outbox_dispatch_interval_seconds: float = 5.0
    outbox_batch_size: int = 20
    outbox_max_dispatch_attempts: int = 5

    # ── Circuit Breaker ──────────────────────────────────────────────
    enable_circuit_breaker: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_seconds: int = 60
    circuit_breaker_half_open_max_calls: int = 3

    # ── Source Protection ────────────────────────────────────────────
    enable_source_protection: bool = True
    source_quarantine_error_threshold: int = 10
    source_quarantine_window_seconds: int = 300
    source_quarantine_duration_seconds: int = 3600

    # ── Notifications ────────────────────────────────────────────────
    notification_webhook_url: str = ""
    notification_webhook_secret: str = ""
    notification_email_enabled: bool = False

    # ── Security ─────────────────────────────────────────────────────
    cors_allowed_origins: str = "*"
    trusted_hosts: str = "*"
    redact_fields: str = "password,secret,token,api_key,authorization"

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def redact_field_list(self) -> list[str]:
        return [f.strip().lower() for f in self.redact_fields.split(",") if f.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


    # ── LLM ──────────────────────────────────────────────────────────
    llm_enabled: bool = True
    llm_provider: str = "mock"  # "openai" or "mock"
    llm_api_key: str = ""
    llm_api_base: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.7
    llm_timeout: int = 30

    # ── Sources ──────────────────────────────────────────────────────
    rss_feeds: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "TrendIntel/1.0"
    reddit_subreddits: str = "technology,marketing,artificial,business"

    # ── Demo ─────────────────────────────────────────────────────────
    demo_mode: bool = True
    demo_tenant_id: str = "demo"
    demo_workspace_id: str = "default"

    # ── Frontend ─────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:5173"


    @property
    def rss_feed_list(self) -> list[str]:
        return [u.strip() for u in self.rss_feeds.split(",") if u.strip()]

    @property
    def reddit_subreddit_list(self) -> list[str]:
        return [s.strip() for s in self.reddit_subreddits.split(",") if s.strip()]

    def validate_config(self) -> list[str]:
        """Fail-fast validation on startup. Returns list of errors."""
        errors: list[str] = []
        if not self.database_url:
            errors.append("SCORING_DATABASE_URL is required")
        if not self.api_key_list:
            errors.append("SCORING_API_KEYS must contain at least one key")
        if not self.admin_api_key or self.admin_api_key == "admin-secret-key":
            if self.env == "prod":
                errors.append("SCORING_ADMIN_API_KEY must be changed from default in prod")
        if self.job_max_attempts < 1:
            errors.append("SCORING_JOB_MAX_ATTEMPTS must be >= 1")
        if self.job_backoff_base_seconds <= 0:
            errors.append("SCORING_JOB_BACKOFF_BASE_SECONDS must be > 0")
        if self.outbox_batch_size < 1:
            errors.append("SCORING_OUTBOX_BATCH_SIZE must be >= 1")
        if self.circuit_breaker_failure_threshold < 1:
            errors.append("SCORING_CIRCUIT_BREAKER_FAILURE_THRESHOLD must be >= 1")
        return errors

    # ── Adaptation & Self-Improvement ────────────────────────────────
    adaptation_enabled: bool = True
    adaptation_mode: str = "suggest_only"  # observe_only / suggest_only / auto_safe / auto_safe_with_audit / approval_required
    adaptation_schedule_seconds: int = 3600  # how often to run evaluation
    adaptation_min_samples: int = 20  # minimum feedback/outcomes before adapting
    adaptation_max_delta_per_update: float = 0.15  # max change per parameter per update (15%)
    adaptation_rollback_on_degradation: bool = True
    adaptation_degradation_threshold: float = 0.10  # 10% degradation triggers rollback
    adaptation_canary_for_risky: bool = True
    adaptation_protected_metrics: str = "alert_precision,recommendation_usefulness"  # comma-separated

    # ── Adaptive Scoring Bounds ──────────────────────────────────────
    adaptive_weight_min: float = 0.1
    adaptive_weight_max: float = 3.0
    adaptive_source_trust_min: float = 0.1
    adaptive_source_trust_max: float = 2.0
    adaptive_threshold_delta_max: float = 20.0  # max absolute threshold change

    # ── Evaluation Windows ───────────────────────────────────────────
    evaluation_windows: str = "24h,7d,30d"
    evaluation_min_sample_threshold: int = 10

    # ── Goal Optimization ────────────────────────────────────────────
    goal_optimization_enabled: bool = True
    goal_max_concurrent_optimizations: int = 5
    goal_multi_metric_constraint: bool = True  # don't optimize one metric at cost of others

    # ── Experimentation ──────────────────────────────────────────────
    experiment_enabled: bool = True
    experiment_max_concurrent: int = 3
    experiment_default_degradation_threshold: float = 0.05
    experiment_min_items_for_verdict: int = 50

    # ── Source Learning ──────────────────────────────────────────────
    source_learning_enabled: bool = True
    source_learning_ewma_alpha: float = 0.1  # exponentially weighted moving average factor
    source_learning_min_samples: int = 10
    source_trust_change_max_per_update: float = 0.1  # max trust change per update cycle

    # ── Pipeline Thresholds (extracted from hardcoded values) ───
    pipeline_alert_score_threshold: float = 50.0
    pipeline_alert_critical_threshold: float = 80.0
    pipeline_recommendation_min_score: float = 10.0
    pipeline_recommendation_high_priority_threshold: float = 50.0
    pipeline_detection_min_count: int = 2
    pipeline_detection_min_value: float = 1.0

    @property
    def protected_metric_list(self) -> list[str]:
        return [m.strip() for m in self.adaptation_protected_metrics.split(",") if m.strip()]

    @property
    def evaluation_window_list(self) -> list[str]:
        return [w.strip() for w in self.evaluation_windows.split(",") if w.strip()]
