"""API routes for contract registry — admin/internal tooling."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from scoring_service.contracts_registry.registry import contract_registry

contracts_router = APIRouter(prefix="/v1/contracts", tags=["contracts"])


@contracts_router.get("/")
def list_contracts(domain: str | None = Query(None)):
    contracts = contract_registry.list_contracts(domain)
    return {
        "contracts": [c.model_dump() for c in contracts],
        "count": len(contracts),
    }


@contracts_router.get("/{name}")
def get_contract(name: str, version: int | None = Query(None)):
    result = contract_registry.get(name, version)
    if not result:
        raise HTTPException(404, f"contract '{name}' not found")
    schema_cls, meta = result
    return {
        "contract": meta.model_dump(),
        "json_schema": schema_cls.model_json_schema(),
    }


@contracts_router.get("/{name}/versions")
def list_versions(name: str):
    versions = contract_registry.list_versions(name)
    if not versions:
        raise HTTPException(404, f"contract '{name}' not found")
    return {"versions": [v.model_dump() for v in versions]}


@contracts_router.post("/{name}/validate")
def validate_payload(name: str, request_body: dict[str, Any], version: int | None = Query(None)):
    return contract_registry.validate(name, request_body, version)


@contracts_router.get("/{name}/compatibility")
def check_compatibility(name: str, old_version: int = Query(...), new_version: int = Query(...)):
    return contract_registry.check_compatibility(name, old_version, new_version)
