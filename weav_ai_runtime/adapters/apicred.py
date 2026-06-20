from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from weav_ai_runtime.contracts import AIRuntimeContext, ModelSpec, UsageRecord
from weav_ai_runtime.factory import AIRuntime


@dataclass(slots=True)
class ApiCredConfig:
    base_url: str = "http://localhost:8103/v1"
    access_token: str = ""
    default_model: str = "gpt-4o"
    timeout_seconds: float = 20.0


class ApiCredCredentialStore:
    """Expose APICred as an OpenAI-compatible provider for AIRuntime."""

    def __init__(self, config: ApiCredConfig) -> None:
        self.config = config

    def get_api_key(self, provider: str, context: AIRuntimeContext) -> str | None:
        _ = context
        if provider != "openai":
            return None
        return self.config.access_token or "apicred"

    def get_base_url(self, provider: str, context: AIRuntimeContext) -> str | None:
        _ = context
        if provider != "openai":
            return None
        return self.config.base_url.rstrip("/")


class ApiCredModelCatalog:
    def __init__(self, config: ApiCredConfig) -> None:
        self.config = config

    def list_models(self, context: AIRuntimeContext, provider: str | None = None) -> dict[str, list[str]]:
        _ = context
        if provider not in {None, "openai", "apicred"}:
            return {}
        models = self._fetch_models()
        return {"openai": models or [self.config.default_model]}

    def resolve_model(
        self,
        context: AIRuntimeContext,
        provider: str | None = None,
        model: str | None = None,
    ) -> ModelSpec:
        _ = context
        if model:
            return ModelSpec(provider="openai", model=model)
        models = self.list_models(context, provider=provider).get("openai", [])
        return ModelSpec(provider="openai", model=models[0] if models else self.config.default_model)

    def _fetch_models(self) -> list[str]:
        headers = {"Accept": "application/json"}
        if self.config.access_token:
            headers["Authorization"] = f"Bearer {self.config.access_token}"
        req = Request(f"{self.config.base_url.rstrip('/')}/models", headers=headers)
        try:
            with urlopen(req, timeout=self.config.timeout_seconds) as resp:
                payload: Any = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []
        if isinstance(payload, list):
            return [str(item.get("name") or item.get("id") or item) for item in payload if item]
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return [str(item.get("id") or item.get("name")) for item in payload["data"] if isinstance(item, dict)]
        return []


class ApiCredUsageSink:
    def record(self, usage: UsageRecord) -> None:
        _ = usage


def build_apicred_runtime(
    *,
    base_url: str = "http://localhost:8103/v1",
    access_token: str = "",
    default_model: str = "gpt-4o",
    tenant: str | None = None,
    user_id: str | None = None,
    purpose: str | None = None,
) -> AIRuntime:
    config = ApiCredConfig(base_url=base_url, access_token=access_token, default_model=default_model)
    context = AIRuntimeContext(tenant=tenant, user_id=user_id, purpose=purpose or "apicred")
    return AIRuntime(
        context=context,
        credentials=ApiCredCredentialStore(config),
        model_catalog=ApiCredModelCatalog(config),
        usage_sink=ApiCredUsageSink(),
    )

