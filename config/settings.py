"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# .envの設定を環境変数へ読み込みます。通常、既存の環境変数は上書きしません。
load_dotenv()


def _positive_int(name: str, default: int) -> int:
    """Read a positive integer from the environment, falling back safely."""
    try:
        # os.getenvは文字列を返すため、数値の設定ではintに変換します。
        value = int(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default


# dataclassは設定値をまとめるクラスの初期化処理などを生成します。
# frozen=Trueにより、作成後の設定オブジェクトへの再代入を禁止します。
@dataclass(frozen=True)
class Settings:
    """Runtime settings whose defaults may be overridden by environment variables."""

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "")
    ollama_connect_timeout_seconds: int = _positive_int("OLLAMA_CONNECT_TIMEOUT_SECONDS", 10)
    ollama_read_timeout_seconds: int = _positive_int(
        # 新設定がなければ旧OLLAMA_TIMEOUT_SECONDS、それもなければ600秒を使います。
        "OLLAMA_READ_TIMEOUT_SECONDS", _positive_int("OLLAMA_TIMEOUT_SECONDS", 600)
    )
    review_chunk_size: int = _positive_int("REVIEW_CHUNK_SIZE", 6000)
    ollama_allowed_hosts: tuple[str, ...] = tuple(
        # カンマ区切りの文字列を、空白除去・小文字化したホスト名のタプルに変換します。
        host.strip().lower()
        for host in os.getenv(
            "OLLAMA_ALLOWED_HOSTS", "localhost,127.0.0.1,::1"
        ).split(",")
        if host.strip()
    )


# モジュール読み込み時に作る共通の設定オブジェクト。app.pyはこれを初期値に使います。
SETTINGS = Settings()
