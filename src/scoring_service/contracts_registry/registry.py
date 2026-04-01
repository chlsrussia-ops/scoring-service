"""Internal contract registry — versioned schemas for events, artifacts, and inter-module data."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Type

from pydantic import BaseModel, ConfigDict, Field


class Compatibility(str, Enum):
    FULL = "full"  # both forward and backward compatible
    BACKWARD = "backward"  # new schema can read old data
    FORWARD = "forward"  # old schema can read new data  
    NONE = "none"  # breaking change


class ContractStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class ContractMeta(BaseModel):
    """Metadata for a registered contract."""
    model_config = ConfigDict(frozen=True)

    name: str
    version: int
    domain: str  # scoring, adaptation, evaluation, workflow, pipeline
    description: str = ""
    compatibility: Compatibility = Compatibility.BACKWARD
    status: ContractStatus = ContractStatus.ACTIVE
    deprecated_by: str | None = None
    schema_hash: str = ""
    fields: list[str] = Field(default_factory=list)
    registered_at: str = ""


class ContractRegistry:
    """In-memory registry of all data contracts with versioning and validation."""

    def __init__(self) -> None:
        self._contracts: dict[str, dict[int, tuple[Type[BaseModel], ContractMeta]]] = {}

    def register(
        self, name: str, version: int, schema: Type[BaseModel],
        domain: str = "general", description: str = "",
        compatibility: Compatibility = Compatibility.BACKWARD,
    ) -> ContractMeta:
        """Register a contract version."""
        if name not in self._contracts:
            self._contracts[name] = {}

        # Compute schema hash from JSON schema
        json_schema = schema.model_json_schema()
        schema_hash = hashlib.sha256(json.dumps(json_schema, sort_keys=True).encode()).hexdigest()[:16]
        fields = list(json_schema.get("properties", {}).keys())

        meta = ContractMeta(
            name=name, version=version, domain=domain,
            description=description, compatibility=compatibility,
            schema_hash=schema_hash, fields=fields,
            registered_at=datetime.now(timezone.utc).isoformat(),
        )

        self._contracts[name][version] = (schema, meta)
        return meta

    def get(self, name: str, version: int | None = None) -> tuple[Type[BaseModel], ContractMeta] | None:
        """Get a contract by name and version. Latest if version not specified."""
        versions = self._contracts.get(name)
        if not versions:
            return None
        if version is not None:
            return versions.get(version)
        latest_v = max(versions.keys())
        return versions[latest_v]

    def get_schema(self, name: str, version: int | None = None) -> Type[BaseModel] | None:
        result = self.get(name, version)
        return result[0] if result else None

    def validate(self, name: str, data: dict[str, Any], version: int | None = None) -> dict[str, Any]:
        """Validate data against a registered contract."""
        result = self.get(name, version)
        if not result:
            return {"valid": False, "error": f"contract '{name}' v{version} not found"}
        schema_cls, meta = result
        try:
            instance = schema_cls.model_validate(data)
            return {"valid": True, "contract": meta.name, "version": meta.version}
        except Exception as exc:
            return {"valid": False, "contract": meta.name, "version": meta.version, "errors": str(exc)[:500]}

    def list_contracts(self, domain: str | None = None) -> list[ContractMeta]:
        """List all contracts, optionally filtered by domain."""
        result = []
        for name, versions in self._contracts.items():
            for version, (_, meta) in sorted(versions.items()):
                if domain and meta.domain != domain:
                    continue
                result.append(meta)
        return result

    def list_versions(self, name: str) -> list[ContractMeta]:
        versions = self._contracts.get(name, {})
        return [meta for _, (_, meta) in sorted(versions.items())]

    def check_compatibility(self, name: str, old_version: int, new_version: int) -> dict[str, Any]:
        """Check if new version is compatible with old version."""
        old = self.get(name, old_version)
        new = self.get(name, new_version)
        if not old or not new:
            return {"compatible": False, "error": "version not found"}

        old_schema, old_meta = old
        new_schema, new_meta = new

        old_fields = set(old_meta.fields)
        new_fields = set(new_meta.fields)

        added = new_fields - old_fields
        removed = old_fields - new_fields
        kept = old_fields & new_fields

        breaking = len(removed) > 0
        
        # Check if removed fields were required in old schema
        old_json = old_schema.model_json_schema()
        required = set(old_json.get("required", []))
        required_removed = removed & required

        verdict = "compatible"
        if required_removed:
            verdict = "breaking"
        elif removed:
            verdict = "warning"

        return {
            "compatible": not bool(required_removed),
            "verdict": verdict,
            "added_fields": sorted(added),
            "removed_fields": sorted(removed),
            "required_removed": sorted(required_removed),
            "kept_fields": sorted(kept),
            "old_hash": old_meta.schema_hash,
            "new_hash": new_meta.schema_hash,
            "same_schema": old_meta.schema_hash == new_meta.schema_hash,
        }

    def deprecate(self, name: str, version: int, deprecated_by: str | None = None) -> bool:
        versions = self._contracts.get(name, {})
        entry = versions.get(version)
        if not entry:
            return False
        schema, meta = entry
        new_meta = meta.model_copy(update={
            "status": ContractStatus.DEPRECATED,
            "deprecated_by": deprecated_by,
        })
        versions[version] = (schema, new_meta)
        return True


# Global singleton
contract_registry = ContractRegistry()
