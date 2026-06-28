import importlib
import asyncio
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


class AsyncCredentials:
    async def get_api_key(self, provider, context):
        return {"openai": f"{context.user_id}-openai-key"}.get(provider)

    async def get_base_url(self, provider, context):
        return None


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


def test_build_router_respects_allowed_provider_policy(monkeypatch):
    runtime = import_runtime(monkeypatch)
    policy = runtime.RuntimePolicy(purpose="docode", allowed_providers=["openai"])

    router = runtime.build_router(runtime.AIRuntimeContext(tenant="default"), Credentials(), policy)

    assert set(router.providers) == {"openai"}


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


def test_runtime_policy_can_supply_fallback_and_deny_models(monkeypatch):
    runtime = import_runtime(monkeypatch)
    context = runtime.AIRuntimeContext()
    fallback_spec = runtime.ModelSpec(provider="qwen", model="qwen-max")
    policy = runtime.RuntimePolicy(purpose="docode", fallback_chain=[fallback_spec], denied_models=["bad-model"])

    fallback = runtime.AIRuntime(context=context, credentials=Credentials(), policy=policy).resolve_model()

    assert fallback.provider == "qwen"
    assert fallback.model == "qwen-max"

    try:
        runtime.AIRuntime(context=context, credentials=Credentials(), policy=policy).resolve_model(provider="openai", model="bad-model")
    except ValueError as exc:
        assert "model_denied:openai:bad-model" in str(exc)
    else:
        raise AssertionError("expected denied model to fail")


def test_normalize_llm_call_result_extracts_text_usage_and_tool_calls(monkeypatch):
    runtime = import_runtime(monkeypatch)

    result = runtime.normalize_llm_call_result(
        {
            "choices": [
                {
                    "message": {
                        "content": "hello",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {"name": "read_file", "arguments": "{\"path\":\"README.md\"}"},
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        },
        provider="openai",
        model="gpt-test",
        purpose="docode",
    )

    assert result.text == "hello"
    assert result.usage.tokens == 5
    assert result.usage.prompt_tokens == 3
    assert result.usage.completion_tokens == 2
    assert result.usage.provider == "openai"
    assert result.tool_calls[0].name == "read_file"
    assert result.tool_calls[0].arguments == {"path": "README.md"}


def test_call_llm_provider_supports_async_completion_client(monkeypatch):
    runtime = import_runtime(monkeypatch)

    class Client:
        async def acomplete(self, prompt, config):
            assert prompt == "hello"
            assert config == {"model": "gpt-test", "temperature": 0.0}
            return {
                "choices": [{"message": {"content": "done"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            }

    result = asyncio.run(runtime.call_llm_provider(Client(), prompt="hello", model="gpt-test", provider="openai", purpose="docode"))

    assert result.text == "done"
    assert result.usage.tokens == 3
    assert result.usage.provider == "openai"
    assert result.usage.model == "gpt-test"
    assert result.usage.purpose == "docode"


def test_call_llm_provider_supports_sync_chat_client(monkeypatch):
    runtime = import_runtime(monkeypatch)

    class Client:
        def chat(self, messages, config):
            assert messages == [{"role": "user", "content": "hello"}]
            assert config == {"model": "gpt-test", "temperature": 0.0}
            return "chat-done"

    result = asyncio.run(runtime.call_llm_provider(Client(), prompt="hello", model="gpt-test"))

    assert result.text == "chat-done"


def test_build_router_async_supports_async_credential_store(monkeypatch):
    runtime = import_runtime(monkeypatch)
    context = runtime.AIRuntimeContext(user_id="u1")

    router = asyncio.run(runtime.build_router_async(context, AsyncCredentials()))

    assert router.providers["openai"] == {
        "provider": "openai",
        "kwargs": {"api_key": "u1-openai-key"},
    }


def test_sync_build_router_rejects_async_credential_store(monkeypatch):
    runtime = import_runtime(monkeypatch)
    ai_runtime = runtime.AIRuntime(context=runtime.AIRuntimeContext(), credentials=AsyncCredentials())

    try:
        ai_runtime.build_router()
    except RuntimeError as exc:
        assert "build_router_async" in str(exc)
    else:
        raise AssertionError("expected async credential store to require build_router_async")
