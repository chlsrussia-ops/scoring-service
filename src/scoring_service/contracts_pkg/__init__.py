"""Contracts package — all Pydantic schemas grouped by domain.

Canonical imports:
  from scoring_service.contracts_pkg.scoring import ScoreRequest, ScoreResult
  from scoring_service.contracts_pkg.adaptation import FeedbackCreate
  from scoring_service.contracts_pkg.platform import TenantOut

Legacy imports still work via shims:
  from scoring_service.contracts import ScoreRequest
  from scoring_service.adaptation_contracts import FeedbackCreate
  from scoring_service.platform_contracts import TenantOut
"""
