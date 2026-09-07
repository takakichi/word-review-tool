"""Minimal HTTP client for the Ollama API."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests

LOGGER = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    """User-safe wrapper for Ollama communication failures."""


def normalize_and_validate_url(base_url: str, allowed_hosts: tuple[str, ...]) -> str:
    """Validate scheme and explicit host allowlist, returning a normalized URL."""
    normalized = base_url.strip().rstrip("/")
    parsed = urlparse(normalized)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise OllamaError("Ollama API URLはhttpまたはhttpsの完全なURLで指定してください。")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise OllamaError("Ollama API URLに認証情報、クエリ、フラグメントは指定できません。")
    if hostname not in allowed_hosts:
        raise OllamaError(
            f"接続先ホスト '{hostname}' は許可されていません。"
            "OLLAMA_ALLOWED_HOSTSへ社内Ollamaホストを追加してください。"
        )
    return normalized


class OllamaClient:
    """Small injectable client used by the review orchestration service."""

    def __init__(
        self, base_url: str, timeout_seconds: int, allowed_hosts: tuple[str, ...]
    ) -> None:
        self.base_url = normalize_and_validate_url(base_url, allowed_hosts)
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.trust_env = False

    def list_models(self) -> list[str]:
        """Return installed Ollama model names."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags", timeout=min(self.timeout_seconds, 15)
            )
            response.raise_for_status()
            payload = response.json()
            return sorted(
                model["name"]
                for model in payload.get("models", [])
                if isinstance(model, dict) and model.get("name")
            )
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            LOGGER.warning("Failed to list Ollama models: %s", type(exc).__name__)
            raise OllamaError(
                "Ollamaからモデル一覧を取得できませんでした。URL、Ollamaの起動状態、"
                "ネットワーク設定を確認してください。"
            ) from exc

    def generate(self, model: str, prompt: str) -> str:
        """Request one non-streaming JSON-formatted review response."""
        if not model.strip():
            raise OllamaError("Ollamaモデルを指定してください。")
        try:
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model.strip(),
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1},
                },
                timeout=self.timeout_seconds,
            )
            if response.status_code == 404:
                raise OllamaError(
                    "指定モデルが見つかりません。Ollamaへモデルをpullしてから再実行してください。"
                )
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise OllamaError(f"Ollamaエラー: {payload['error']}")
            generated = payload.get("response")
            if not isinstance(generated, str):
                raise OllamaError("Ollamaレスポンスにresponse文字列がありません。")
            return generated
        except OllamaError:
            raise
        except requests.Timeout as exc:
            LOGGER.warning("Ollama request timed out.")
            raise OllamaError("Ollama APIがタイムアウトしました。") from exc
        except (requests.RequestException, ValueError) as exc:
            LOGGER.warning("Ollama request failed: %s", type(exc).__name__)
            raise OllamaError(
                "Ollamaへのレビュー要求に失敗しました。接続状態とモデルを確認してください。"
            ) from exc

