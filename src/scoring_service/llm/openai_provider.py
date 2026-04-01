"""OpenAI-compatible LLM provider."""
from __future__ import annotations

import httpx

from scoring_service.config import Settings
from scoring_service.llm.base import LlmProvider, LlmRequest, LlmResponse


class OpenAIProvider(LlmProvider):
    provider_name = "openai"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.llm_api_key
        self.api_base = settings.llm_api_base.rstrip("/")
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate(self, request: LlmRequest) -> LlmResponse:
        if not self.api_key:
            return LlmResponse(text="", provider=self.provider_name, model=self.model, error="No API key configured")

        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": request.max_tokens,
                        "temperature": request.temperature,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            choice = data["choices"][0]
            usage = data.get("usage", {})
            return LlmResponse(
                text=choice["message"]["content"],
                tokens_used=usage.get("total_tokens", 0),
                model=data.get("model", self.model),
                provider=self.provider_name,
            )
        except Exception as e:
            return LlmResponse(text="", provider=self.provider_name, model=self.model, error=str(e))
