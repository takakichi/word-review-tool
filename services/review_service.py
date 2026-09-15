"""Review response parsing and multi-chunk orchestration."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from pydantic import ValidationError

from models.review_models import ChunkReviewResult, ParseFailure, ReviewResponse, ReviewRunResult
from services.ollama_service import OllamaClient, OllamaError
from services.prompt_service import build_full_prompt
# このサービスはUIを直接呼びません。進捗通知は引数で渡されたコールバックに任せます。


def _extract_json_text(raw_response: str) -> str:
    """Remove a common Markdown fence without guessing arbitrary prose."""
    stripped = raw_response.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    # 正規表現で回答全体がコードフェンスに包まれている場合だけ、中身を取り出します。
    # DOTALLは改行も含めて一致させる指定。任意の説明文からJSONを推測して抜き出すことはしません。
    return fenced.group(1).strip() if fenced else stripped


def parse_review_response(raw_response: str) -> ReviewResponse:
    """Parse and validate an LLM JSON response."""
    try:
        payload = json.loads(_extract_json_text(raw_response))
        # json.loadsで「文字列 → Pythonの辞書等」、model_validateで「構造と値の検証」を行います。
        return ReviewResponse.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ValueError(f"LLMレスポンスのJSON検証に失敗しました: {exc}") from exc


def run_review(
    client: OllamaClient,
    model: str,
    instruction_prompt: str,
    document_chunks: list[str],
    on_progress: Callable[[int, int], None] | None = None,
    on_update: Callable[[ReviewRunResult], None] | None = None,
    previous_result: ReviewRunResult | None = None,
    chunk_numbers: list[int] | None = None,
) -> ReviewRunResult:
    """Keep each completed attempt and optionally retry only selected failed chunks."""
    # deep=Trueで前回結果の内部リスト等もコピーし、呼び出し元が持つ結果を直接書き換えません。
    result = previous_result.model_copy(deep=True) if previous_result else ReviewRunResult()
    total = len(document_chunks)
    targets = list(range(1, total + 1)) if chunk_numbers is None else list(dict.fromkeys(chunk_numbers))
    # 初回は全チャンク、再実行時は指定番号のみ。dict.fromkeysで順序を保ったまま重複を除きます。
    if any(index < 1 or index > total for index in targets):
        raise ValueError("再実行するチャンク番号が対象範囲外です。")
    if previous_result is not None and any(
        # 保存済みの失敗チャンクだけを再実行し、成功済みチャンクの再送信を防ぎます。
        index not in result.chunk_results or result.chunk_results[index].failure is None
        for index in targets
    ):
        raise ValueError("再実行の対象には失敗したチャンクだけを指定してください。")
    if on_update:
        # Callableは「呼び出せる関数」の型ヒント。Noneなら通知なしで処理できます。
        # コピーを渡すことで、通知先が受け取った途中結果を後続処理から独立させます。
        on_update(result.model_copy(deep=True))
    for index in targets:
        if on_progress:
            on_progress(index, total)
        attempt = ChunkReviewResult(chunk_number=index)
        # 1回分の状態を新しく作り、このチャンクの成功・失敗をここへ記録します。
        try:
            raw = client.generate(
                model, build_full_prompt(instruction_prompt, document_chunks[index - 1])
            )
            attempt.raw_response = raw
            attempt.reviews = parse_review_response(raw).reviews
        except OllamaError as exc:
            # 失敗をデータとして記録するので、例外で全体を終了せず次のチャンクへ進めます。
            attempt.failure = ParseFailure(
                chunk_number=index, error=str(exc), raw_response="", kind="request"
            )
        except ValueError as exc:
            # JSON解析失敗では生レスポンスを残し、画面で原因を確認できるようにします。
            attempt.failure = ParseFailure(
                chunk_number=index, error=str(exc), raw_response=attempt.raw_response
            )
        result.chunk_results[index] = attempt
        # 同じ番号の前回状態を置き換え、再実行による結果の二重追加を防ぎます。
        _rebuild_aggregates(result)
        if on_update:
            # 毎チャンク終了時に通知するため、UIは全件完了前でも結果を保存・表示できます。
            on_update(result.model_copy(deep=True))
    return result


def _rebuild_aggregates(result: ReviewRunResult) -> None:
    """Recompute exports from the latest attempt of each chunk."""
    ordered = [result.chunk_results[index] for index in sorted(result.chunk_results)]
    # 最新チャンク結果を唯一の元データとし、表示・出力用の一覧を毎回作り直します。
    # 下の二重forの内包表記は「各チャンク内の指摘一覧」を1つのリストへ平坦化します。
    result.reviews = [item for attempt in ordered for item in attempt.reviews]
    result.failures = [attempt.failure for attempt in ordered if attempt.failure is not None]
    result.raw_responses = [attempt.raw_response for attempt in ordered]
    severity_order = {"high": 0, "medium": 1, "low": 2}
    result.reviews.sort(
        # lambdaは短い無名関数。ページ番号 → 重要度 → 観点名の順で並べるキーを返します。
        key=lambda item: (item.page, severity_order[item.severity], item.category)
    )
