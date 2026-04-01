"""LLM provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class LlmRequest(BaseModel):
    prompt: str
    system: str = ""
    max_tokens: int = 1024
    temperature: float = 0.7


class LlmResponse(BaseModel):
    text: str
    tokens_used: int = 0
    model: str = ""
    provider: str = ""
    error: str | None = None


class LlmProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def generate(self, request: LlmRequest) -> LlmResponse:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...
