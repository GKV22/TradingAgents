"""Settings model dropdown: provider listings, filtering, cache, endpoints."""

import pytest
from fastapi.testclient import TestClient

from web import model_list


class _Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data


@pytest.fixture
def calls(monkeypatch):
    seen = []

    def fake_get(url, headers, timeout):
        seen.append((url, headers))
        if "anthropic" in url:
            return _Resp({"data": [{"id": "claude-sonnet-5"}, {"id": "claude-haiku-4-5"}]})
        if "googleapis" in url:
            return _Resp({"models": [
                {"name": "models/gemini-3.5-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
            ]})
        return _Resp({"data": [{"id": "gpt-5.5"}, {"id": "text-embedding-3-large"},
                               {"id": "gpt-image-1"}, {"id": "whisper-1"}, {"id": "gpt-4.1"}]})

    monkeypatch.setattr(model_list.requests, "get", fake_get)
    for env in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.setenv(env, "test-key")
    return seen


def test_openai_listing_keeps_only_chat_models(calls):
    assert model_list.fetch_models("openai") == ["gpt-4.1", "gpt-5.5"]
    url, headers = calls[0]
    assert url == "https://api.openai.com/v1/models"
    assert headers["Authorization"] == "Bearer test-key"


def test_anthropic_and_google_listings(calls):
    assert model_list.fetch_models("anthropic") == ["claude-haiku-4-5", "claude-sonnet-5"]
    assert model_list.fetch_models("google") == ["gemini-3.5-flash"]
    google_url, google_headers = calls[1]
    assert "test-key" not in google_url  # key travels in a header, never the URL
    assert google_headers["x-goog-api-key"] == "test-key"


def test_unlisted_provider_and_missing_key_are_clear_errors(calls, monkeypatch):
    with pytest.raises(model_list.ModelListError, match="no model listing"):
        model_list.fetch_models("azure")
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    with pytest.raises(model_list.ModelListError, match="DEEPSEEK_API_KEY is not set"):
        model_list.fetch_models("deepseek")
    assert calls == []


def test_http_error_message_does_not_leak_key(calls, monkeypatch):
    monkeypatch.setattr(model_list.requests, "get", lambda *a, **k: _Resp({}, status=401))
    with pytest.raises(model_list.ModelListError) as exc:
        model_list.fetch_models("openai")
    assert "401" in str(exc.value) and "test-key" not in str(exc.value)


def test_refresh_caches_and_overrides_built_in_list(calls, tmp_path):
    cache = tmp_path / "model_cache.json"
    before = model_list.model_lists(cache)["openai"]
    assert before["source"] == "built-in" and before["refreshable"]
    entry = model_list.refresh("openai", cache)
    assert entry["models"] == ["gpt-4.1", "gpt-5.5"] and entry["source"] == "provider"
    assert model_list.model_lists(cache)["openai"]["models"] == ["gpt-4.1", "gpt-5.5"]
    assert "custom" not in model_list.model_lists(cache)["deepseek"]["models"]
    assert model_list.model_lists(cache)["glm"]["refreshable"] is False


def test_refresh_endpoint_rejects_unknown_provider():
    from web.server import app

    resp = TestClient(app).post("/api/models/..%2Fetc/refresh")
    assert resp.status_code >= 400  # never reaches a provider fetch
    resp = TestClient(app).post("/api/models/azure/refresh")
    assert resp.status_code == 400


def test_models_endpoint_lists_providers(monkeypatch, tmp_path):
    from web.server import app

    monkeypatch.setattr(model_list, "CACHE_PATH", tmp_path / "none.json")
    monkeypatch.setattr(model_list.model_lists, "__defaults__", (tmp_path / "none.json",))
    data = TestClient(app).get("/api/models").json()
    assert {"openai", "anthropic", "google", "deepseek"} <= data.keys()
    assert data["deepseek"]["models"] == ["deepseek-v4-flash", "deepseek-v4-pro"]
