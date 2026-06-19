from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class AIRuntimeContext:
    tenant: str | None = None
    user_id: str | None = None
    purpose: str | None = None


@dataclass(frozen=True, slots=True)
class ModelSpec:
    provider: str
    model: str


@dataclass(frozen=True, slots=True)
class UsageRecord:
    tokens: int
    cost: float
    provider: str | None = None
    model: str | None = None
    tenant: str | None = None
    user_id: str | None = None
    purpose: str | None = None


class CredentialStore(Protocol):
    def get_api_key(self, provider: str, context: AIRuntimeContext) -> str | None: ...

    def get_base_url(self, provider: str, context: AIRuntimeContext) -> str | None: ...


class ModelCatalog(Protocol):
    def list_models(self, context: AIRuntimeContext, provider: str | None = None) -> dict[str, list[str]]: ...

    def resolve_model(
        self,
        context: AIRuntimeContext,
        provider: str | None = None,
        model: str | None = None,
    ) -> ModelSpec: ...


class UsageSink(Protocol):
    def record(self, usage: UsageRecord) -> None: ...

