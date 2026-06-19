from __future__ import annotations

import logging
from dataclasses import dataclass

from weav_ai_core.llm import LLMRouter
from weav_ai_providers import build_provider

from .contracts import AIRuntimeContext, CredentialStore, ModelCatalog, ModelSpec, UsageSink


logger = logging.getLogger(__name__)

SUPPORTED_CHAT_PROVIDERS = ("openai", "anthropic", "google", "ollama", "deepseek", "qwen", "zhipu")


def build_router(context: AIRuntimeContext, credentials: CredentialStore) -> LLMRouter:
    """Build an LLMRouter from a product-specific credential store."""
    router = LLMRouter()
    for provider in SUPPORTED_CHAT_PROVIDERS:
        api_key = credentials.get_api_key(provider, context)
        base_url = credentials.get_base_url(provider, context)
        if not api_key and provider != "ollama":
            continue
        if provider == "ollama" and not base_url:
            continue

        kwargs: dict[str, str] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        try:
            router.register(provider, build_provider(provider, **kwargs))
        except Exception as exc:
            logger.warning("Skipping AI provider %s after registration failure: %s", provider, exc)
            continue
    return router


@dataclass(slots=True)
class AIRuntime:
    context: AIRuntimeContext
    credentials: CredentialStore
    model_catalog: ModelCatalog | None = None
    usage_sink: UsageSink | None = None

    def build_router(self) -> LLMRouter:
        return build_router(self.context, self.credentials)

    def resolve_model(self, provider: str | None = None, model: str | None = None) -> ModelSpec:
        if self.model_catalog is not None:
            return self.model_catalog.resolve_model(self.context, provider=provider, model=model)
        return ModelSpec(provider=provider or "openai", model=model or "gpt-4o")
