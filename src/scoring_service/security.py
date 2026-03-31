from __future__ import annotations
from fastapi import Header, HTTPException, Request, status
from scoring_service.config import Settings

async def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    settings: Settings = request.app.state.settings
    if x_api_key is None or x_api_key not in settings.api_key_list:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing api key")
    return x_api_key
