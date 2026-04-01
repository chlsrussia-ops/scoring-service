"""Infrastructure layer — cross-cutting concerns.

Modules:
- circuit_breaker: Circuit breaker pattern for external calls
- correlation: Request correlation ID tracking
- rate_limit: API rate limiting
- source_protection: Source quarantine / health tracking
- tracing: OpenTelemetry integration
- observability: Prometheus metrics
- diagnostics: Logging configuration
"""
