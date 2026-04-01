"""Demo API routes."""
from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from scoring_service.config import Settings
from scoring_service.demo.runner import DemoRunner
from scoring_service.sources.manager import SourceManager

router = APIRouter(prefix="/v1/demo", tags=["demo"])


def _get_db(request: Request) -> Session:
    return request.app.state.session_factory()


@router.post("/seed")
async def demo_seed(request: Request) -> dict:
    db = _get_db(request)
    settings: Settings = request.app.state.settings
    try:
        runner = DemoRunner(db, settings)
        return runner.seed()
    finally:
        db.close()


@router.post("/sync-sources")
async def demo_sync_sources(request: Request) -> dict:
    db = _get_db(request)
    settings: Settings = request.app.state.settings
    try:
        runner = DemoRunner(db, settings)
        runner.ensure_tenant()
        mgr = SourceManager(db)
        results = await mgr.sync_all(settings.demo_tenant_id)
        return {"results": results}
    finally:
        db.close()


@router.post("/run-analysis")
async def demo_run_analysis(request: Request) -> dict:
    db = _get_db(request)
    settings: Settings = request.app.state.settings
    try:
        runner = DemoRunner(db, settings)
        return await runner.run_analysis()
    finally:
        db.close()


@router.post("/generate-ai")
async def demo_generate_ai(request: Request) -> dict:
    db = _get_db(request)
    settings: Settings = request.app.state.settings
    try:
        runner = DemoRunner(db, settings)
        return await runner.generate_ai()
    finally:
        db.close()


@router.post("/dispatch-alerts")
async def demo_dispatch_alerts(request: Request) -> dict:
    db = _get_db(request)
    settings: Settings = request.app.state.settings
    try:
        runner = DemoRunner(db, settings)
        return await runner.dispatch_alerts()
    finally:
        db.close()


@router.post("/run-all")
async def demo_run_all(request: Request) -> dict:
    db = _get_db(request)
    settings: Settings = request.app.state.settings
    try:
        runner = DemoRunner(db, settings)
        return await runner.run_all()
    finally:
        db.close()


@router.get("/status")
async def demo_status(request: Request) -> dict:
    db = _get_db(request)
    settings: Settings = request.app.state.settings
    try:
        runner = DemoRunner(db, settings)
        return runner.get_status()
    finally:
        db.close()


@router.post("/generate-all-narratives")
async def generate_all_narratives(request: Request) -> dict:
    db = _get_db(request)
    settings: Settings = request.app.state.settings
    try:
        runner = DemoRunner(db, settings)
        return await runner.generate_ai()
    finally:
        db.close()
