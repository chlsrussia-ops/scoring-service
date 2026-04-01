"""Shim — canonical location is scoring_service.db.models_pkg.

All models re-exported here for backward compatibility.
"""
from scoring_service.db.models_pkg import *  # noqa: F401,F403
from scoring_service.db.models_pkg._base import Base, _utcnow  # noqa: F401
