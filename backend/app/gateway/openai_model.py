"""OpenAI 兼容模型后端（httpx 直连，适配 OpenAI / Ollama / vLLM 等 /v1/chat/completions）。"""
from __future__ import annotations

import httpx

from ..config import Settings
from .base import ChatMessage, ModelBackend, ModelResponse


class OpenAIModelBackend(ModelBackend):
    def __init__(self, cfg: "Settings", endpoint) -> None:
        super().__init__(
            id=endpoint.id,
            kind=endpoint.kind,
            input_price_per_mtok=endpoint.input_price_per_mtok,
            output_price_per_mtok=endpoint.output_price_per_mtok,
            enabled=endpoint.enabled,
        )
        self._base_url = endpoint.base_url.rstrip("/")
        self._api_key = endpoint.api_key
        self._timeout = cfg.http_timeout_seconds

    def chat(self, messages: list[ChatMessage], temperature: float = 0.0) -> ModelResponse:
        url = f"{self._base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self.id,
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))

        self.stats["calls"] += 1
        self.stats.setdefault("input_tokens", 0)
        self.stats.setdefault("output_tokens", 0)
        self.stats["input_tokens"] += input_tokens
        self.stats["output_tokens"] += output_tokens

        return ModelResponse(
            model_id=self.id,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=data,
        )
