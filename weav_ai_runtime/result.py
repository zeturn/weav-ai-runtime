from __future__ import annotations

import json
from typing import Any

from .contracts import LLMCallResult, ToolCall, UsageRecord


async def call_llm_provider(
    client: Any,
    *,
    prompt: str,
    model: str,
    provider: str | None = None,
    purpose: str | None = None,
    config: Any | None = None,
) -> LLMCallResult:
    completion_config = config if config is not None else default_completion_config(model)
    if hasattr(client, "acomplete"):
        try:
            response = await client.acomplete(prompt=prompt, model=model)
        except TypeError:
            response = await client.acomplete(prompt, completion_config)
        return normalize_llm_call_result(response, provider=provider, model=model, purpose=purpose)
    if hasattr(client, "complete"):
        try:
            response = client.complete(prompt=prompt, model=model)
        except TypeError:
            response = client.complete(prompt, completion_config)
        if hasattr(response, "__await__"):
            response = await response
        return normalize_llm_call_result(response, provider=provider, model=model, purpose=purpose)
    if hasattr(client, "achat"):
        messages = [{"role": "user", "content": prompt}]
        try:
            response = await client.achat(messages=messages, model=model)
        except TypeError:
            response = await client.achat(messages, completion_config)
        return normalize_llm_call_result(response, provider=provider, model=model, purpose=purpose)
    if hasattr(client, "chat"):
        messages = [{"role": "user", "content": prompt}]
        try:
            response = client.chat(messages=messages, model=model)
        except TypeError:
            response = client.chat(messages, completion_config)
        if hasattr(response, "__await__"):
            response = await response
        return normalize_llm_call_result(response, provider=provider, model=model, purpose=purpose)
    raise RuntimeError("provider client does not expose a supported chat/completion method")


def default_completion_config(model: str) -> dict[str, Any]:
    return {"model": model, "temperature": 0.0}


def normalize_llm_call_result(
    response: Any,
    *,
    provider: str | None = None,
    model: str | None = None,
    purpose: str | None = None,
) -> LLMCallResult:
    if isinstance(response, LLMCallResult):
        return response
    if isinstance(response, str):
        return LLMCallResult(text=response, raw=response)

    usage = usage_record_from_response(response, provider=provider, model=model, purpose=purpose)
    text = extract_text(response)
    if text is None:
        text = str(response)
    return LLMCallResult(
        text=text,
        tool_calls=extract_tool_calls(response),
        usage=usage,
        raw=get_field(response, "raw") or response,
    )


def usage_record_from_response(
    response: Any,
    *,
    provider: str | None = None,
    model: str | None = None,
    purpose: str | None = None,
) -> UsageRecord | None:
    usage = get_field(response, "usage") or get_field(response, "usage_metadata")
    if usage is None and not any(get_field(response, key) is not None for key in ("prompt_tokens", "completion_tokens", "total_tokens", "tokens", "cost")):
        return None

    prompt_tokens = int_or_none(first_present(usage, "prompt_tokens", "input_tokens", "prompt", "input"))
    completion_tokens = int_or_none(first_present(usage, "completion_tokens", "output_tokens", "completion", "output"))
    total_tokens = int_or_none(first_present(usage, "total_tokens", "tokens", "total"))
    cost = float_or_none(first_present(usage, "cost", "total_cost", "amount"))

    if prompt_tokens is None:
        prompt_tokens = int_or_none(first_present(response, "prompt_tokens", "input_tokens"))
    if completion_tokens is None:
        completion_tokens = int_or_none(first_present(response, "completion_tokens", "output_tokens"))
    if total_tokens is None:
        total_tokens = int_or_none(first_present(response, "total_tokens", "tokens"))
    if cost is None:
        cost = float_or_none(first_present(response, "cost", "total_cost"))

    tokens = total_tokens
    if tokens is None and (prompt_tokens is not None or completion_tokens is not None):
        tokens = (prompt_tokens or 0) + (completion_tokens or 0)
    if tokens is None and cost is None:
        return None
    return UsageRecord(
        tokens=tokens or 0,
        cost=cost or 0.0,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        provider=provider,
        model=model,
        purpose=purpose,
    )


def extract_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        direct = first_present(value, "output_text", "text", "content")
        if direct is not None:
            return content_to_text(direct)
        choices = value.get("choices")
        if isinstance(choices, list) and choices:
            return extract_text(choices[0])
        message = value.get("message")
        if message is not None:
            return extract_text(message)
        data = value.get("data")
        if data is not None:
            return extract_text(data)
        output = value.get("output")
        if output is not None:
            return content_to_text(output)
        return None

    for attr in ("output_text", "text", "content"):
        if hasattr(value, attr):
            return content_to_text(getattr(value, attr))
    if hasattr(value, "choices"):
        choices = getattr(value, "choices")
        if isinstance(choices, list) and choices:
            return extract_text(choices[0])
    if hasattr(value, "message"):
        return extract_text(getattr(value, "message"))
    return None


def content_to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            text = extract_text(item)
            if text is not None:
                parts.append(text)
        return "\n".join(parts) if parts else None
    if isinstance(value, dict):
        direct = first_present(value, "text", "content", "value")
        return content_to_text(direct) if direct is not None else None
    return str(value)


def extract_tool_calls(value: Any) -> list[ToolCall]:
    raw_calls = first_present(value, "tool_calls", "function_calls")
    if raw_calls is None:
        message = first_present(value, "message")
        if message is not None:
            raw_calls = first_present(message, "tool_calls", "function_calls")
    if raw_calls is None:
        choices = first_present(value, "choices")
        if isinstance(choices, list) and choices:
            return extract_tool_calls(choices[0])
    if not isinstance(raw_calls, list):
        return []
    calls: list[ToolCall] = []
    for item in raw_calls:
        parsed = parse_tool_call(item)
        if parsed is not None:
            calls.append(parsed)
    return calls


def parse_tool_call(value: Any) -> ToolCall | None:
    function = first_present(value, "function") or value
    name = first_present(function, "name")
    if not name:
        return None
    raw_args = first_present(function, "arguments", "args") or {}
    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {"raw": raw_args}
    elif isinstance(raw_args, dict):
        args = dict(raw_args)
    else:
        args = {"value": raw_args}
    return ToolCall(id=str(first_present(value, "id")) if first_present(value, "id") is not None else None, name=str(name), arguments=args)


def first_present(value: Any, *keys: str) -> object | None:
    for key in keys:
        candidate = get_field(value, key)
        if candidate is not None:
            return candidate
    return None


def get_field(value: Any, key: str) -> object | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(key)
    if hasattr(value, key):
        return getattr(value, key)
    return None


def int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
