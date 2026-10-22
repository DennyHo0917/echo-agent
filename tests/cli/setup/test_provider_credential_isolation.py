"""Exercise wizard listing and the real SDK with fake, origin-bound keys."""

import json
from contextlib import ExitStack
from unittest.mock import patch

import httpx
import openai
import pytest

from echo_agent.cli import setup
from echo_agent.cli.setup import providers


@pytest.fixture
def wizard(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "official-key-must-stay-at-openai")
    monkeypatch.delenv("CHEAPER_INFERENCE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    requests = []

    def endpoint(request):
        requests.append((request.url.host, request.url.path, request.headers.get("authorization")))
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "gpt-5.4-mini", "context_length": 128000}]})
        return httpx.Response(200, json={
            "id": "test", "object": "chat.completion", "created": 0, "model": "gpt-5.4-mini",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    sdk = openai.AsyncOpenAI

    def client(**kwargs):
        return sdk(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(endpoint)))

    def get(url, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(endpoint)) as client:
            return client.get(url, **kwargs)

    monkeypatch.setattr(openai, "AsyncOpenAI", client)
    monkeypatch.setattr(httpx, "get", get)

    def run(*, entry_id="cheaperinference", password="", existing=None, base=""):
        config = existing if existing is not None else {}
        model = providers.find(entry_id).fallback_models
        model = model[0] if model else "test-model"

        def select(message, choices, **kwargs):
            return "skip" if any(c[0] == "skip" for c in choices) else model

        with ExitStack() as stack:
            for target, value in [
                ("select_grouped", entry_id), ("password", password), ("text", base),
            ]:
                stack.enter_context(patch.object(setup.ui, target, return_value=value))
            stack.enter_context(patch.object(setup.ui, "select", side_effect=select))
            setup.setup_model(config)
        return config, requests

    return run


def test_brand_environment_key_is_used_for_listing_and_inference_without_persisting_secret(wizard, monkeypatch):
    monkeypatch.setenv("CHEAPER_INFERENCE_API_KEY", "cheaper-only-key")
    config, requests = wizard()
    assert len(requests) == 3  # models, context windows, and the SDK's verification request
    assert all(host == "api.cheaperinference.com" and auth == "Bearer cheaper-only-key"
               for host, _, auth in requests)
    provider = config["models"]["providers"][0]
    assert provider["apiKeyEnv"] == "CHEAPER_INFERENCE_API_KEY"
    assert "apiKey" not in provider
    assert "cheaper-only-key" not in json.dumps(config)
    assert config["models"]["modelWindows"]["gpt-5.4-mini"] == 128000


def test_missing_brand_key_never_sends_the_official_key(wizard):
    config, requests = wizard()
    assert requests == []
    assert config["models"]["providers"][0]["apiKeyEnv"] == "CHEAPER_INFERENCE_API_KEY"


def test_manually_entered_key_wins_over_environment(wizard, monkeypatch):
    monkeypatch.setenv("CHEAPER_INFERENCE_API_KEY", "environment-key")
    config, requests = wizard(password="entered-key")
    assert all(auth == "Bearer entered-key" for _, _, auth in requests)
    assert config["models"]["providers"][0]["apiKey"] == "entered-key"
    assert "apiKeyEnv" not in config["models"]["providers"][0]


def test_existing_explicit_environment_binding_is_preserved(wizard, monkeypatch):
    monkeypatch.setenv("MY_GATEWAY_KEY", "bound-key")
    config, requests = wizard(existing={"models": {"providers": [{
        "name": "openai", "apiBase": "https://api.cheaperinference.com/v1/", "apiKeyEnv": "MY_GATEWAY_KEY",
    }]}})
    assert config["models"]["providers"][0]["apiKeyEnv"] == "MY_GATEWAY_KEY"
    assert all(auth == "Bearer bound-key" for _, _, auth in requests)


def test_switching_provider_does_not_reuse_saved_official_key(wizard):
    config, requests = wizard(existing={"models": {"providers": [{
        "name": "openai", "apiBase": "https://api.openai.com/v1", "apiKey": "saved-official-key",
    }]}})
    assert requests == []
    assert "saved-official-key" not in json.dumps(config)


def test_changing_custom_endpoint_does_not_reuse_its_saved_key(wizard):
    config, requests = wizard(entry_id="custom", base="https://new-gateway.invalid/v1", existing={
        "models": {"providers": [{
            "name": "openai", "apiBase": "https://old-gateway.invalid/v1", "apiKey": "old-gateway-key",
        }]},
    })
    assert requests == [("new-gateway.invalid", "/v1/chat/completions", "Bearer not-required")]
    assert "old-gateway-key" not in json.dumps(config)


def test_official_openai_environment_still_works(wizard):
    config, requests = wizard(entry_id="openai")
    assert all(host == "api.openai.com" and auth == "Bearer official-key-must-stay-at-openai"
               for host, _, auth in requests)
    assert config["models"]["providers"][0]["apiKeyEnv"] == "OPENAI_API_KEY"
