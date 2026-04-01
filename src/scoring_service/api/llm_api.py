"""LLM API routes."""
from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.db.models import DigestReport, LlmGeneration
from scoring_service.llm.service import LlmService

router = APIRouter(prefix="/v1/llm", tags=["llm"])


def _get_db(request: Request) -> Session:
    return request.app.state.session_factory()


def _tenant_id(request: Request) -> str:
    return request.query_params.get("tenant_id", "demo")


@router.post("/trends/{trend_id}/generate-summary")
async def generate_trend_summary(trend_id: int, request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    settings: Settings = request.app.state.settings
    try:
        svc = LlmService(db, settings)
        gen = await svc.generate_trend_summary(trend_id, tid)
        return _gen_to_dict(gen)
    except ValueError as e:
        return {"error": str(e)}
    finally:
        db.close()


@router.post("/recommendations/{rec_id}/enhance")
async def enhance_recommendation(rec_id: int, request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    settings: Settings = request.app.state.settings
    try:
        svc = LlmService(db, settings)
        gen = await svc.enhance_recommendation(rec_id, tid)
        return _gen_to_dict(gen)
    except ValueError as e:
        return {"error": str(e)}
    finally:
        db.close()


@router.post("/digests/generate")
async def generate_digest(request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    settings: Settings = request.app.state.settings
    try:
        svc = LlmService(db, settings)
        digest = await svc.generate_digest(tid)
        return {
            "id": digest.id,
            "title": digest.title,
            "summary": digest.summary,
            "top_trends": digest.top_trends_json,
            "top_recommendations": digest.top_recommendations_json,
            "key_risks": digest.key_risks_json,
            "stats": digest.stats_json,
            "created_at": str(digest.created_at),
        }
    finally:
        db.close()


@router.get("/digests")
async def list_digests(request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        items = db.query(DigestReport).filter(DigestReport.tenant_id == tid).order_by(DigestReport.created_at.desc()).limit(20).all()
        return {
            "total": len(items),
            "items": [
                {
                    "id": d.id, "title": d.title, "summary": d.summary,
                    "stats": d.stats_json, "created_at": str(d.created_at),
                }
                for d in items
            ],
        }
    finally:
        db.close()


@router.get("/generations")
async def list_generations(request: Request) -> dict:
    db = _get_db(request)
    tid = _tenant_id(request)
    try:
        limit = min(int(request.query_params.get("limit", "50")), 200)
        items = db.query(LlmGeneration).filter(LlmGeneration.tenant_id == tid).order_by(LlmGeneration.generated_at.desc()).limit(limit).all()
        return {
            "total": len(items),
            "items": [_gen_to_dict(g) for g in items],
        }
    finally:
        db.close()


def _gen_to_dict(g: LlmGeneration) -> dict:
    return {
        "id": g.id,
        "entity_type": g.entity_type,
        "entity_id": g.entity_id,
        "prompt_template": g.prompt_template,
        "provider": g.provider,
        "model": g.model,
        "output_text": g.output_text,
        "tokens_used": g.tokens_used,
        "error": g.error,
        "generated_at": str(g.generated_at),
    }
