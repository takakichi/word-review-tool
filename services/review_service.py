"""Review response parsing and multi-chunk orchestration."""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from pydantic import ValidationError

from models.review_models import ParseFailure, ReviewResponse, ReviewRunResult
from services.ollama_service import OllamaClient
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
) -> ReviewRunResult:
    """Review every chunk; retain invalid raw responses without aborting the run."""
    result = ReviewRunResult()
    total = len(document_chunks)
    for index, chunk in enumerate(document_chunks, start=1):
        if on_progress:
            on_progress(index, total)
        raw = client.generate(model, build_full_prompt(instruction_prompt, chunk))
        result.raw_responses.append(raw)
        try:
            parsed = parse_review_response(raw)
            result.reviews.extend(parsed.reviews)
        except ValueError as exc:
            result.failures.append(
                ParseFailure(
                    chunk_number=index,
                    error=str(exc),
                    raw_response=raw,
                )
            )
    severity_order = {"high": 0, "medium": 1, "low": 2}
    result.reviews.sort(
        key=lambda item: (item.page, severity_order[item.severity], item.category)
    )
    return result
