from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class AIRuntimeContext:
    tenant: str | None = None
    user_id: str | None = None
    purpose: str | None = None


@dataclass(frozen=True, slots=True)
class ModelSpec:
    provider: str
    model: str
    supports_tools: bool = False
    supports_json_schema: bool = False
    supports_streaming: bool = False
    context_window: int | None = None
    input_cost_per_mtok: float | None = None
    output_cost_per_mtok: float | None = None


@dataclass(frozen=True, slots=True)
class UsageRecord:
    tokens: int
    cost: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    provider: str | None = None
    model: str | None = None
    tenant: str | None = None
    user_id: str | None = None
    purpose: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    purpose: str
    max_tokens: int | None = None
    max_cost: float | None = None
    allowed_providers: list[str] = field(default_factory=list)
    denied_models: list[str] = field(default_factory=list)
    fallback_chain: list[ModelSpec] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str | None
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMCallResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: UsageRecord | None = None
    raw: Any = None


class CredentialStore(Protocol):
    def get_api_key(self, provider: str, context: AIRuntimeContext) -> str | None: ...

    def get_base_url(self, provider: str, context: AIRuntimeContext) -> str | None: ...


class AsyncCredentialStore(Protocol):
    async def get_api_key(self, provider: str, context: AIRuntimeContext) -> str | None: ...

    async def get_base_url(self, provider: str, context: AIRuntimeContext) -> str | None: ...


class ModelCatalog(Protocol):
    def list_models(self, context: AIRuntimeContext, provider: str | None = None) -> dict[str, list[str]]: ...

    def resolve_model(
        self,
        context: AIRuntimeContext,
        provider: str | None = None,
        model: str | None = None,
    ) -> ModelSpec: ...


class AsyncModelCatalog(Protocol):
    async def list_models(self, context: AIRuntimeContext, provider: str | None = None) -> dict[str, list[str]]: ...

    async def resolve_model(
        self,
        context: AIRuntimeContext,
        provider: str | None = None,
        model: str | None = None,
    ) -> ModelSpec: ...


class UsageSink(Protocol):
    def record(self, usage: UsageRecord) -> None: ...


class AsyncUsageSink(Protocol):
    async def record(self, usage: UsageRecord) -> None: ...
