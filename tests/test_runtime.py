import importlib
import sys
import types


def install_dependency_stubs(monkeypatch):
    core = types.ModuleType("weav_ai_core")
    core.__path__ = []

    class LLMRouter:
        def __init__(self):
            self.providers = {}

        def register(self, name, provider):
            self.providers[name] = provider

    llm = types.ModuleType("weav_ai_core.llm")
    llm.LLMRouter = LLMRouter

    providers = types.ModuleType("weav_ai_providers")

    def build_provider(provider, **kwargs):
        if provider == "anthropic":
            raise RuntimeError("provider unavailable")
        return {"provider": provider, "kwargs": kwargs}

    providers.build_provider = build_provider

    monkeypatch.setitem(sys.modules, "weav_ai_core", core)
    monkeypatch.setitem(sys.modules, "weav_ai_core.llm", llm)
    monkeypatch.setitem(sys.modules, "weav_ai_providers", providers)


def import_runtime(monkeypatch):
    install_dependency_stubs(monkeypatch)
    for name in ["weav_ai_runtime", "weav_ai_runtime.factory"]:
        sys.modules.pop(name, None)
    return importlib.import_module("weav_ai_runtime")


class Credentials:
    def get_api_key(self, provider, context):
        return {"openai": "openai-key", "anthropic": "anthropic-key"}.get(provider)

    def get_base_url(self, provider, context):
        return {"ollama": "http://localhost:11434"}.get(provider)


class Catalog:
    def resolve_model(self, context, provider=None, model=None):
        return type("Resolved", (), {"provider": provider, "model": model})()


def test_build_router_registers_available_providers_and_logs_failures(monkeypatch, caplog):
    runtime = import_runtime(monkeypatch)

    router = runtime.build_router(runtime.AIRuntimeContext(tenant="default"), Credentials())

    assert router.providers["openai"] == {
        "provider": "openai",
        "kwargs": {"api_key": "openai-key"},
    }
    assert router.providers["ollama"] == {
        "provider": "ollama",
        "kwargs": {"base_url": "http://localhost:11434"},
    }
    assert "anthropic" not in router.providers
    assert "Skipping AI provider anthropic" in caplog.text


def test_runtime_resolve_model_uses_catalog_or_default(monkeypatch):
    runtime = import_runtime(monkeypatch)
    context = runtime.AIRuntimeContext()

    with_catalog = runtime.AIRuntime(context=context, credentials=Credentials(), model_catalog=Catalog())
    resolved = with_catalog.resolve_model(provider="qwen", model="qwen-max")

    assert resolved.provider == "qwen"
    assert resolved.model == "qwen-max"

    fallback = runtime.AIRuntime(context=context, credentials=Credentials()).resolve_model()

    assert fallback.provider == "openai"
    assert fallback.model == "gpt-4o"
