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
    # URLをスキーム・ホスト名などへ分解し、許可する接続先か確認します。
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise OllamaError("Ollama API URLはhttpまたはhttpsの完全なURLで指定してください。")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise OllamaError("Ollama API URLに認証情報、クエリ、フラグメントは指定できません。")
    if hostname not in allowed_hosts:
        # 文書の誤送信を防ぐ、明示的な許可リストです。未登録ホストへは要求を送りません。
        raise OllamaError(
            f"接続先ホスト '{hostname}' は許可されていません。"
            "OLLAMA_ALLOWED_HOSTSへ社内Ollamaホストを追加してください。"
        )
    return normalized


class OllamaClient:
    """Small injectable client used by the review orchestration service."""

    def __init__(
        self,
        base_url: str,
        connect_timeout_seconds: int,
        read_timeout_seconds: int,
        allowed_hosts: tuple[str, ...],
    ) -> None:
        # __init__はオブジェクト生成時に実行されます。self.xxxに保存した設定を各メソッドで使います。
        self.base_url = normalize_and_validate_url(base_url, allowed_hosts)
        if connect_timeout_seconds <= 0 or read_timeout_seconds <= 0:
            raise OllamaError("タイムアウトは正の秒数で指定してください。")
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self.session = requests.Session()
        # SessionでHTTP接続を再利用します。環境変数のプロキシ等は使わない設定です。
        self.session.trust_env = False

    def list_models(self) -> list[str]:
        """Return installed Ollama model names."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/tags",
                timeout=(self.connect_timeout_seconds, min(self.read_timeout_seconds, 15)),
            )
            response.raise_for_status()
            # HTTPの4xx/5xxを例外に変換します。成功時はそのまま次へ進みます。
            payload = response.json()
            return sorted(
                # 応答のmodels配列から名前を取り出し、画面で選びやすいように並べ替えます。
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
            # POSTのjson引数にはPythonの辞書を渡します。requestsがJSONへ変換して送信します。
            # stream=Falseは生成完了まで待つ方式、format="json"はLLMへの出力形式の指定です。
            # 形式指定だけでは不正な回答を防ぎ切れないため、受信後に別サービスで検証します。
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model.strip(),
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1},
                },
                timeout=(self.connect_timeout_seconds, self.read_timeout_seconds),
                # timeoutのタプルは（接続待ち, 応答の受信待ち）。全処理の厳密な時間上限ではありません。
            )
            if response.status_code == 404:
                raise OllamaError(
                    "指定モデルが見つかりません。Ollamaへモデルをpullしてから再実行してください。"
                )
            response.raise_for_status()
            payload = response.json()
            # ここで解析するのはAPI応答の外側のJSON。responseフィールド内のLLM回答はまだ文字列です。
            if payload.get("error"):
                raise OllamaError(f"Ollamaエラー: {payload['error']}")
            generated = payload.get("response")
            if not isinstance(generated, str):
                raise OllamaError("Ollamaレスポンスにresponse文字列がありません。")
            return generated
        except OllamaError:
            # 既に利用者向けの専用例外になっていれば、メッセージを変えずそのまま伝えます。
            raise
        except requests.ConnectTimeout as exc:
            # 具体的な例外を先に捕まえ、接続待ちと応答待ちを区別して案内します。
            LOGGER.warning("Ollama connection timed out.")
            raise OllamaError(
                f"Ollama APIへの接続がタイムアウトしました（{self.connect_timeout_seconds}秒）。"
            ) from exc
        except requests.ReadTimeout as exc:
            LOGGER.warning("Ollama response wait timed out.")
            raise OllamaError(
                f"Ollama APIの応答待ちがタイムアウトしました（{self.read_timeout_seconds}秒）。"
                "応答待ち時間を増やして、失敗チャンクを再実行してください。"
            ) from exc
        except requests.Timeout as exc:
            LOGGER.warning("Ollama request timed out.")
            raise OllamaError("Ollama APIがタイムアウトしました。") from exc
        except (requests.RequestException, ValueError) as exc:
            LOGGER.warning("Ollama request failed: %s", type(exc).__name__)
            raise OllamaError(
                "Ollamaへのレビュー要求に失敗しました。接続状態とモデルを確認してください。"
            ) from exc
