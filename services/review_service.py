"""Review response parsing and multi-chunk orchestration."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from pydantic import ValidationError

from models.review_models import ChunkReviewResult, ParseFailure, ReviewResponse, ReviewRunResult
from services.ollama_service import OllamaClient, OllamaError
from services.prompt_service import build_full_prompt


def _extract_json_text(raw_response: str) -> str:
    """Remove a common Markdown fence without guessing arbitrary prose."""
    stripped = raw_response.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    return fenced.group(1).strip() if fenced else stripped


def parse_review_response(raw_response: str) -> ReviewResponse:
    """Parse and validate an LLM JSON response."""
    try:
        payload = json.loads(_extract_json_text(raw_response))
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
    result = previous_result.model_copy(deep=True) if previous_result else ReviewRunResult()
    total = len(document_chunks)
    targets = list(range(1, total + 1)) if chunk_numbers is None else list(dict.fromkeys(chunk_numbers))
    if any(index < 1 or index > total for index in targets):
        raise ValueError("再実行するチャンク番号が対象範囲外です。")
    if previous_result is not None and any(
        index not in result.chunk_results or result.chunk_results[index].failure is None
        for index in targets
    ):
        raise ValueError("再実行の対象には失敗したチャンクだけを指定してください。")
    if on_update:
        on_update(result.model_copy(deep=True))
    for index in targets:
        if on_progress:
            on_progress(index, total)
        attempt = ChunkReviewResult(chunk_number=index)
        try:
            raw = client.generate(
                model, build_full_prompt(instruction_prompt, document_chunks[index - 1])
            )
            attempt.raw_response = raw
            attempt.reviews = parse_review_response(raw).reviews
        except OllamaError as exc:
            attempt.failure = ParseFailure(
                chunk_number=index, error=str(exc), raw_response="", kind="request"
            )
        except ValueError as exc:
            attempt.failure = ParseFailure(
                chunk_number=index, error=str(exc), raw_response=attempt.raw_response
            )
        result.chunk_results[index] = attempt
        _rebuild_aggregates(result)
        if on_update:
            on_update(result.model_copy(deep=True))
    return result


def _rebuild_aggregates(result: ReviewRunResult) -> None:
    """Recompute exports from the latest attempt of each chunk."""
    ordered = [result.chunk_results[index] for index in sorted(result.chunk_results)]
    result.reviews = [item for attempt in ordered for item in attempt.reviews]
    result.failures = [attempt.failure for attempt in ordered if attempt.failure is not None]
    result.raw_responses = [attempt.raw_response for attempt in ordered]
    severity_order = {"high": 0, "medium": 1, "low": 2}
    result.reviews.sort(
        key=lambda item: (item.page, severity_order[item.severity], item.category)
    )
