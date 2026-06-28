from __future__ import annotations

import logging
from dataclasses import dataclass

from weav_ai_core.llm import LLMRouter
from weav_ai_providers import build_provider

from .contracts import (
    AIRuntimeContext,
    AsyncCredentialStore,
    AsyncModelCatalog,
    AsyncUsageSink,
    CredentialStore,
    ModelCatalog,
    ModelSpec,
    RuntimePolicy,
    UsageSink,
)


logger = logging.getLogger(__name__)

SUPPORTED_CHAT_PROVIDERS = ("openai", "anthropic", "google", "ollama", "deepseek", "qwen", "zhipu")


def build_router(context: AIRuntimeContext, credentials: CredentialStore, policy: RuntimePolicy | None = None) -> LLMRouter:
    """Build an LLMRouter from a product-specific credential store."""
    router = LLMRouter()
    for provider in providers_for_policy(policy):
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


async def build_router_async(context: AIRuntimeContext, credentials: AsyncCredentialStore, policy: RuntimePolicy | None = None) -> LLMRouter:
    """Build an LLMRouter when credential resolution requires async I/O."""
    router = LLMRouter()
    for provider in providers_for_policy(policy):
        api_key = await credentials.get_api_key(provider, context)
        base_url = await credentials.get_base_url(provider, context)
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
    credentials: CredentialStore | AsyncCredentialStore
    model_catalog: ModelCatalog | AsyncModelCatalog | None = None
    usage_sink: UsageSink | AsyncUsageSink | None = None
    policy: RuntimePolicy | None = None

    def build_router(self) -> LLMRouter:
        if is_async_credential_store(self.credentials):
            raise RuntimeError("async credentials require build_router_async()")
        return build_router(self.context, self.credentials, self.policy)

    async def build_router_async(self) -> LLMRouter:
        if is_async_credential_store(self.credentials):
            return await build_router_async(self.context, self.credentials, self.policy)
        return build_router(self.context, self.credentials, self.policy)

    def resolve_model(self, provider: str | None = None, model: str | None = None) -> ModelSpec:
        if self.model_catalog is not None:
            if is_async_model_catalog(self.model_catalog):
                raise RuntimeError("async model catalog requires resolve_model_async()")
            return apply_model_policy(self.model_catalog.resolve_model(self.context, provider=provider, model=model), self.policy)
        return apply_model_policy(default_model_spec(provider=provider, model=model, policy=self.policy), self.policy)

    async def resolve_model_async(self, provider: str | None = None, model: str | None = None) -> ModelSpec:
        if self.model_catalog is not None:
            if is_async_model_catalog(self.model_catalog):
                return apply_model_policy(await self.model_catalog.resolve_model(self.context, provider=provider, model=model), self.policy)
            return apply_model_policy(self.model_catalog.resolve_model(self.context, provider=provider, model=model), self.policy)
        return apply_model_policy(default_model_spec(provider=provider, model=model, policy=self.policy), self.policy)


def providers_for_policy(policy: RuntimePolicy | None) -> tuple[str, ...]:
    if policy is None or not policy.allowed_providers:
        return SUPPORTED_CHAT_PROVIDERS
    allowed = {provider.strip().lower() for provider in policy.allowed_providers if provider.strip()}
    return tuple(provider for provider in SUPPORTED_CHAT_PROVIDERS if provider in allowed)


def default_model_spec(provider: str | None, model: str | None, policy: RuntimePolicy | None) -> ModelSpec:
    if provider or model:
        return ModelSpec(provider=provider or "openai", model=model or "gpt-4o")
    if policy is not None and policy.fallback_chain:
        return policy.fallback_chain[0]
    return ModelSpec(provider="openai", model="gpt-4o")


def apply_model_policy(spec: ModelSpec, policy: RuntimePolicy | None) -> ModelSpec:
    if policy is None:
        return spec
    if policy.allowed_providers and spec.provider not in {provider.strip().lower() for provider in policy.allowed_providers}:
        raise ValueError(f"provider_not_allowed:{spec.provider}")
    if spec.model in set(policy.denied_models):
        raise ValueError(f"model_denied:{spec.provider}:{spec.model}")
    return spec


def is_async_credential_store(credentials: CredentialStore | AsyncCredentialStore) -> bool:
    return is_async_callable(getattr(credentials, "get_api_key", None)) or is_async_callable(getattr(credentials, "get_base_url", None))


def is_async_model_catalog(catalog: ModelCatalog | AsyncModelCatalog) -> bool:
    return is_async_callable(getattr(catalog, "resolve_model", None)) or is_async_callable(getattr(catalog, "list_models", None))


def is_async_callable(candidate: object) -> bool:
    import inspect

    return inspect.iscoroutinefunction(candidate)
