"""Sources API routes."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from scoring_service.db.models import DataSource, SourceStatus, SourceType
from scoring_service.sources.manager import SourceManager

router = APIRouter(prefix="/v1/sources", tags=["sources"])


def _get_db(request: Request) -> Session:
    return request.app.state.session_factory()


def _tenant_id(request: Request) -> str:
    return request.query_params.get("tenant_id", "demo")


class CreateSourceRequest(BaseModel):
    name: str
    source_type: str
    config_json: dict = {}
    enabled: bool = True


@router.get("")
async def list_sources(request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        items = db.query(DataSource).filter(DataSource.tenant_id == tid).all()
        return {
            "total": len(items),
            "items": [_source_to_dict(s) for s in items],
        }
    finally:
        db.close()


@router.post("")
async def create_source(body: CreateSourceRequest, request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        ds = DataSource(
            tenant_id=tid,
            name=body.name,
            source_type=body.source_type,
            config_json=body.config_json,
            enabled=body.enabled,
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)
        return _source_to_dict(ds)
    finally:
        db.close()


@router.post("/{source_id}/test")
async def test_source(source_id: int, request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        source = db.query(DataSource).filter(DataSource.id == source_id, DataSource.tenant_id == tid).first()
        if not source:
            return {"error": "Source not found"}
        mgr = SourceManager(db)
        result = await mgr.test_source(source)
        return result.model_dump()
    finally:
        db.close()


@router.post("/{source_id}/sync")
async def sync_source(source_id: int, request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        source = db.query(DataSource).filter(DataSource.id == source_id, DataSource.tenant_id == tid).first()
        if not source:
            return {"error": "Source not found"}
        mgr = SourceManager(db)
        result = await mgr.sync_source(source, tid)
        return result
    finally:
        db.close()


@router.get("/{source_id}/health")
async def source_health(source_id: int, request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        source = db.query(DataSource).filter(DataSource.id == source_id, DataSource.tenant_id == tid).first()
        if not source:
            return {"error": "Source not found"}
        return {
            "id": source.id,
            "name": source.name,
            "status": source.status.value if hasattr(source.status, "value") else source.status,
            "items_fetched": source.items_fetched,
            "items_normalized": source.items_normalized,
            "failure_count": source.failure_count,
            "last_sync_at": str(source.last_sync_at) if source.last_sync_at else None,
            "last_error": source.last_error,
        }
    finally:
        db.close()


def _source_to_dict(s: DataSource) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "source_type": s.source_type.value if hasattr(s.source_type, "value") else s.source_type,
        "status": s.status.value if hasattr(s.status, "value") else s.status,
        "enabled": s.enabled,
        "config_json": s.config_json,
        "items_fetched": s.items_fetched,
        "items_normalized": s.items_normalized,
        "failure_count": s.failure_count,
        "last_sync_at": str(s.last_sync_at) if s.last_sync_at else None,
        "last_error": s.last_error,
        "created_at": str(s.created_at),
    }
