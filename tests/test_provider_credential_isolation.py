"""Keep implicit official credentials away from compatible third-party origins."""

from unittest.mock import patch

import pytest

from echo_agent.config.schema import ProviderConfig
from echo_agent.models.providers import create_provider


@pytest.mark.parametrize("base", [
    "https://api.cheaperinference.com/v1", "http://localhost:11434/v1",
    "https://api.openai.com.attacker.invalid/v1", "http://api.openai.com/v1",
    "https://api.openai.com:8443/v1", "https://api.openai.com@attacker.invalid/v1",
    "https://api.openai.com:invalid/v1",
])
def test_custom_origin_does_not_inherit_official_key(monkeypatch, base):
    monkeypatch.setenv("OPENAI_API_KEY", "official-secret")
    with patch("echo_agent.models.providers.openai_provider.OpenAIProvider._build_client"):
        provider = create_provider(ProviderConfig(name="openai", api_base=base, models=["m"]))
    assert provider.api_key == "not-required"


@pytest.mark.parametrize("base", ["", "https://api.openai.com/v1", "https://api.openai.com:443/v1"])
def test_official_origin_retains_conventional_environment_discovery(monkeypatch, base):
    monkeypatch.setenv("OPENAI_API_KEY", "official-secret")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    with patch("echo_agent.models.providers.openai_provider.OpenAIProvider._build_client"):
        provider = create_provider(ProviderConfig(name="openai", api_base=base, models=["m"]))
    assert provider.api_key == "official-secret"


def test_sdk_base_url_override_cannot_forward_implicit_official_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "official-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://third-party.invalid/v1")
    with patch("echo_agent.models.providers.openai_provider.OpenAIProvider._build_client") as build:
        with pytest.raises(ValueError, match="requires api_key"):
            create_provider(ProviderConfig(name="openai", models=["m"]))
    build.assert_not_called()


@pytest.mark.parametrize("base", ["", "https://api.cheaperinference.com/v1"])
def test_missing_explicit_environment_source_fails_before_client_creation(monkeypatch, base):
    monkeypatch.setenv("OPENAI_API_KEY", "official-secret")
    monkeypatch.delenv("SELECTED_GATEWAY_KEY", raising=False)
    with patch("echo_agent.models.providers.openai_provider.OpenAIProvider._build_client") as build:
        with pytest.raises(ValueError, match="SELECTED_GATEWAY_KEY"):
            create_provider(ProviderConfig(name="openai", api_base=base, api_key_env="SELECTED_GATEWAY_KEY", models=["m"]))
    build.assert_not_called()


@pytest.mark.parametrize("source", ["explicit_key", "named_environment", "credential_pool"])
def test_explicit_custom_endpoint_credentials_are_preserved(monkeypatch, source):
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-official-secret")
    monkeypatch.delenv("SELECTED_GATEWAY_KEY", raising=False)
    config = ProviderConfig(name="openai", api_base="https://custom.invalid/v1", models=["m"])
    if source == "explicit_key":
        config.api_key, config.api_key_env = "intended-key", "SELECTED_GATEWAY_KEY"
    elif source == "named_environment":
        monkeypatch.setenv("SELECTED_GATEWAY_KEY", "intended-key")
        config.api_key_env = "SELECTED_GATEWAY_KEY"
    else:
        config.credential_pool, config.api_key_env = ["intended-key"], "SELECTED_GATEWAY_KEY"
    with patch("echo_agent.models.providers.openai_provider.OpenAIProvider._build_client"):
        provider = create_provider(config)
    inner = provider._inner if source == "credential_pool" else provider
    assert inner.api_key == "intended-key"
