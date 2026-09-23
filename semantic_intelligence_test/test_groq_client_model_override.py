from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

from app.ai.groq_client import GroqClient


def _make_client_with_stubbed_groq():

    client = GroqClient(
        api_key="dummy",
        base_url=None,
        model="primary-model",
        max_retries=0,
    )

    # Stub the underlying SDK.
    stub_sdk = MagicMock()

    captured: List[Dict[str, Any]] = []

    def create(**kwargs):
        captured.append(kwargs)
        response = MagicMock()
        choice = MagicMock()
        message = MagicMock()
        message.content = '{"ok": true}'
        message.reasoning = None
        choice.message = message
        response.choices = [choice]
        response.usage = None
        return response

    stub_sdk.chat.completions.create.side_effect = create

    client._client = stub_sdk
    client._ensure_configured = lambda: None  # bypass key/model check

    return client, captured


def test_default_model_is_used_when_no_override():

    client, captured = _make_client_with_stubbed_groq()

    client.generate_structured(
        prompt="hello",
        schema={"type": "object", "properties": {}, "required": []},
        schema_name="x",
    )

    assert len(captured) == 1
    assert captured[0]["model"] == "primary-model"


def test_model_override_uses_requested_model():

    client, captured = _make_client_with_stubbed_groq()

    client.generate_structured(
        prompt="hello",
        schema={"type": "object", "properties": {}, "required": []},
        schema_name="x",
        model="fallback-model",
    )

    assert len(captured) == 1
    assert captured[0]["model"] == "fallback-model"


def test_blank_model_override_falls_back_to_default():

    client, captured = _make_client_with_stubbed_groq()

    client.generate_structured(
        prompt="hello",
        schema={"type": "object", "properties": {}, "required": []},
        schema_name="x",
        model="   ",
    )

    assert len(captured) == 1
    assert captured[0]["model"] == "primary-model"


def test_reasoning_effort_none_omits_parameter():

    client, captured = _make_client_with_stubbed_groq()

    client.generate_structured(
        prompt="hello",
        schema={"type": "object", "properties": {}, "required": []},
        schema_name="x",
        reasoning_effort=None,
        model="fallback-model",
    )

    # Even though the client's constructor default is "medium",
    # the explicit None must result in the parameter being absent.
    assert "reasoning_effort" not in captured[0]