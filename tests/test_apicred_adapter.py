import importlib
import io
import sys
import types


def install_dependency_stubs(monkeypatch):
    core = types.ModuleType("weav_ai_core")
    core.__path__ = []
    llm = types.ModuleType("weav_ai_core.llm")

    class LLMRouter:
        def __init__(self):
            self.providers = {}

        def register(self, name, provider):
            self.providers[name] = provider

    llm.LLMRouter = LLMRouter
    providers = types.ModuleType("weav_ai_providers")
    providers.build_provider = lambda provider, **kwargs: {"provider": provider, "kwargs": kwargs}
    monkeypatch.setitem(sys.modules, "weav_ai_core", core)
    monkeypatch.setitem(sys.modules, "weav_ai_core.llm", llm)
    monkeypatch.setitem(sys.modules, "weav_ai_providers", providers)


def import_runtime(monkeypatch):
    install_dependency_stubs(monkeypatch)
    for name in list(sys.modules):
        if name == "weav_ai_runtime" or name.startswith("weav_ai_runtime."):
            sys.modules.pop(name, None)
    return importlib.import_module("weav_ai_runtime")


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'[{"name":"llm-m1"},{"id":"llm-m2"}]'


def test_build_apicred_runtime_uses_openai_compatible_provider(monkeypatch):
    runtime_mod = import_runtime(monkeypatch)
    monkeypatch.setattr("weav_ai_runtime.adapters.apicred.urlopen", lambda req, timeout: Response())

    runtime = runtime_mod.build_apicred_runtime(base_url="http://api.test/v1", access_token="tok", tenant="t1")
    router = runtime.build_router()
    model = runtime.resolve_model()

    assert runtime.context.tenant == "t1"
    assert router.providers["openai"] == {
        "provider": "openai",
        "kwargs": {"api_key": "tok", "base_url": "http://api.test/v1"},
    }
    assert model.provider == "openai"
    assert model.model == "llm-m1"

