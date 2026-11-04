"""Model names for the Settings dropdowns.

Each provider starts from the built-in catalog. "Refresh" asks the provider's
own list-models API (with the API key from the environment) and caches the
result, so a model can be picked from what the provider actually serves
instead of typed from memory. Providers without a usable listing keep the
catalog list plus the UI's "Custom…" option.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from tradingagents.llm_clients.api_key_env import get_api_key_env
from tradingagents.llm_clients.model_catalog import get_known_models

CACHE_PATH = Path.home() / ".tradingagents" / "model_cache.json"
_TIMEOUT = 20

# OpenAI-compatible GET {base}/models listings.
_OPENAI_STYLE = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "xai": "https://api.x.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
}
LISTABLE = frozenset(_OPENAI_STYLE) | {"anthropic", "google"}

# OpenAI's listing also returns embedding, image, audio and moderation models.
_NOT_CHAT = re.compile(
    r"embed|tts|whisper|dall-e|image|audio|realtime|transcribe|moderation|search|"
    r"computer-use|codex|babbage|davinci|sora|veo|imagen|aqa|learnlm", re.I)


class ModelListError(RuntimeError):
    """A refresh failed; the message is safe to show (never contains a key)."""


def _key(provider: str) -> str | None:
    env = get_api_key_env(provider)
    return os.getenv(env) if env else None


def _get(url: str, headers: dict[str, str]) -> Any:
    try:
        r = requests.get(url, headers=headers, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise ModelListError(f"could not reach {provider_host(url)} ({type(exc).__name__})") from None
    if r.status_code != 200:
        raise ModelListError(f"{provider_host(url)} returned HTTP {r.status_code}")
    return r.json()


def provider_host(url: str) -> str:
    return url.split("/")[2] if "//" in url else url


def fetch_models(provider: str) -> list[str]:
    """Ask the provider which chat models this API key can use."""
    if provider not in LISTABLE:
        raise ModelListError(f"{provider} has no model listing; use Custom")
    key = _key(provider)
    if get_api_key_env(provider) and not key:
        raise ModelListError(f"{get_api_key_env(provider)} is not set")

    if provider == "anthropic":
        data = _get("https://api.anthropic.com/v1/models?limit=1000",
                    {"x-api-key": key or "", "anthropic-version": "2023-06-01"})
        ids = [m["id"] for m in data.get("data", [])]
    elif provider == "google":
        # Key in a header, not the URL, so it never lands in logs.
        data = _get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
                    {"x-goog-api-key": key or ""})
        ids = [m["name"].removeprefix("models/") for m in data.get("models", [])
               if "generateContent" in m.get("supportedGenerationMethods", [])]
    else:
        base = os.getenv("OLLAMA_BASE_URL") if provider == "ollama" else None
        base = (base or _OPENAI_STYLE[provider]).rstrip("/")
        data = _get(f"{base}/models", {"Authorization": f"Bearer {key}"} if key else {})
        ids = [m["id"] for m in data.get("data", [])]

    ids = sorted({i for i in ids if isinstance(i, str) and i and not _NOT_CHAT.search(i)})
    if not ids:
        raise ModelListError(f"{provider} returned no chat models")
    return ids


def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def model_lists(path: Path = CACHE_PATH) -> dict[str, dict]:
    """Per provider: the models to offer, where they came from, and whether
    a refresh is possible."""
    cache = _load_cache(path)
    out = {}
    for provider, models in get_known_models().items():
        out[provider] = {"models": [m for m in models if m != "custom"],
                         "source": "built-in", "fetched_at": None}
    for provider in LISTABLE:
        out.setdefault(provider, {"models": [], "source": "built-in", "fetched_at": None})
    for provider, entry in cache.items():
        if provider in out and entry.get("models"):
            out[provider] = {"models": entry["models"], "source": "provider",
                             "fetched_at": entry.get("fetched_at")}
    for provider, entry in out.items():
        entry["refreshable"] = provider in LISTABLE
    return out


def refresh(provider: str, path: Path = CACHE_PATH) -> dict:
    models = fetch_models(provider)
    cache = _load_cache(path)
    cache[provider] = {"models": models,
                       "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    return model_lists(path)[provider]
