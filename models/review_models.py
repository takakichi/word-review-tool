"""Pydantic models for validated review results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
# モデルは「データに何が入るか」の定義です。UIやAPI処理から共通で利用します。
# 型ヒントに加え、Pydanticは値の検証や辞書への変換を担当します。


class ReviewItem(BaseModel):
    """A single issue identified by the language model."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    # 未定義フィールドは無視し、文字列の前後の空白を除去します。

    # Fieldは追加の制約。ge=1は1以上、min_length=1は空文字を禁止する意味です。
    page: int = Field(ge=1)
    category: str = Field(min_length=1)
    severity: Literal["high", "medium", "low"]
    # Literalは許可する値を列挙します。これ以外の重要度は検証エラーになります。
    target_text: str = Field(min_length=1)
    issue: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)


class ReviewResponse(BaseModel):
    """Expected top-level Ollama JSON response."""

    model_config = ConfigDict(extra="ignore")

    reviews: list[ReviewItem] = Field(default_factory=list)
    # default_factoryはモデルを作るたびに新しいリストを生成します。


class ParseFailure(BaseModel):
    """Non-fatal information retained when an LLM response is invalid."""

    # 元のチャンク番号、利用者向けエラー、解析できなかった応答をまとめます。
    # 通信失敗時は生レスポンスがないため空文字を入れ、kindで失敗種別を区別します。
    chunk_number: int = Field(ge=1)
    error: str
    raw_response: str
    kind: Literal["parse", "request"] = "parse"


class ChunkReviewResult(BaseModel):
    """Latest attempt for one chunk; replacements prevent duplicate retry results."""

    # 1チャンクの最新状態。failureがNoneならそのチャンクは成功です。
    # 「指摘が0件」と「処理が失敗」は別の状態として表現します。
    chunk_number: int = Field(ge=1)
    reviews: list[ReviewItem] = Field(default_factory=list)
    failure: ParseFailure | None = None
    raw_response: str = ""


class ReviewRunResult(BaseModel):
    """Aggregated output from all review chunks."""

    # reviews/failures/raw_responsesは画面や出力用にまとめ直した一覧です。
    reviews: list[ReviewItem] = Field(default_factory=list)
    failures: list[ParseFailure] = Field(default_factory=list)
    raw_responses: list[str] = Field(default_factory=list)
    chunk_results: dict[int, ChunkReviewResult] = Field(default_factory=dict)
    # チャンク番号をキーに最新結果を管理。再実行は同じキーを上書きして重複を防ぎます。
