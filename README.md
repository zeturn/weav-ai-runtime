# weav-ai-runtime

Runtime assembly contracts for WeavInt AI.

`weav-ai-runtime` defines the reusable boundary between AI primitives and product-specific infrastructure such as credential storage, model catalogs, usage recording, and provider routing.

## Scope

This package exposes:

- `AIRuntimeContext` for tenant, user, and purpose metadata
- `CredentialStore`, `ModelCatalog`, and `UsageSink` protocols
- `ModelSpec` and `UsageRecord` data contracts
- `AIRuntime` and `build_router()` for assembling provider routing

## Package Relationship

The AI packages are intended to be consumed in this order:

1. `weav-ai-core` provides shared primitives and compatibility imports.
2. `weav-ai-providers` exposes provider construction and model discovery.
3. `weav-ai-runtime` assembles credentials, model catalog, routing, and usage contracts.
4. `weav-server-ai-adapter` connects the reusable runtime to `weav_server` infrastructure.

## Installation

```bash
python -m pip install git+https://github.com/zeturn/weav-ai-runtime.git@main
```

For local development:

```bash
python -m pip install -e ".[dev]" --no-deps
```

## Usage

```python
from weav_ai_runtime import AIRuntime, AIRuntimeContext

context = AIRuntimeContext(tenant="default", user_id="user_123", purpose="chat")
runtime = AIRuntime(context=context, credentials=my_credential_store)
router = runtime.build_router()
model = runtime.resolve_model()
```

## Development

Run the local quality checks:

```bash
python -m pytest
python -m build --wheel
```

## Release Notes

This package is currently in migration bootstrap status. Before cutting a production release, pin `weav-ai-core` and `weav-ai-providers` to tags or published package versions instead of tracking `main`.
