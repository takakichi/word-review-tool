import pytest
from unittest.mock import Mock

from services.review_service import parse_review_response, run_review
from services.ollama_service import OllamaError


VALID_RESPONSE = (
    '{"reviews":[{"page":1,"category":"曖昧な表現","severity":"medium",'
    '"target_text":"必要に応じて","issue":"条件が不明","suggestion":"条件を明記"}]}'
)


def test_request_failure_keeps_successful_chunks_and_publishes_partial_updates() -> None:
    client = Mock()
    client.generate.side_effect = [VALID_RESPONSE, OllamaError("timeout"), '{"reviews":[]}']
    updates = []
    result = run_review(client, "model", "instructions", ["one", "two", "three"], on_update=updates.append)
    assert len(result.reviews) == 1
    assert result.failures[0].chunk_number == 2
    assert result.failures[0].kind == "request"
    assert len(result.chunk_results) == 3
    assert len(updates) == 4
    assert len(updates[1].reviews) == 1
    assert updates[0].chunk_results == {}


def test_retry_only_failed_chunk_replaces_failure_without_duplicates() -> None:
    client = Mock()
    client.generate.side_effect = [VALID_RESPONSE, OllamaError("timeout")]
    first = run_review(client, "model", "instructions", ["one", "two"])
    retry_client = Mock()
    retry_client.generate.return_value = VALID_RESPONSE
    result = run_review(
        retry_client, "model", "instructions", ["one", "two"],
        previous_result=first, chunk_numbers=[2],
    )
    retry_client.generate.assert_called_once()
    assert "two" in retry_client.generate.call_args.args[1]
    assert len(result.reviews) == 2
    assert result.failures == []
    assert len(first.failures) == 1  # Caller-owned previous result is not mutated.


def test_repeated_retry_failure_keeps_success_and_allows_later_retry() -> None:
    client = Mock()
    client.generate.side_effect = [VALID_RESPONSE, "invalid JSON"]
    first = run_review(client, "model", "instructions", ["one", "two"])
    client.generate.side_effect = [OllamaError("timeout")]
    result = run_review(client, "model", "instructions", ["one", "two"], previous_result=first, chunk_numbers=[2])
    assert len(result.reviews) == 1
    assert len(result.failures) == 1
    assert result.failures[0].kind == "request"


def test_retry_successful_chunk_is_rejected() -> None:
    client = Mock()
    client.generate.return_value = VALID_RESPONSE
    first = run_review(client, "model", "instructions", ["one"])
    with pytest.raises(ValueError, match="失敗したチャンク"):
        run_review(client, "model", "instructions", ["one"], previous_result=first, chunk_numbers=[1])


def test_parse_valid_review_json() -> None:
    parsed = parse_review_response(
        '{"reviews":[{"page":3,"category":"曖昧な表現","severity":"medium",'
        '"target_text":"必要に応じて","issue":"条件が不明","suggestion":"条件を明記"}]}'
    )
    assert parsed.reviews[0].page == 3
    assert parsed.reviews[0].severity == "medium"


def test_parse_json_code_fence() -> None:
    parsed = parse_review_response("```json\n{\"reviews\": []}\n```")
    assert parsed.reviews == []


def test_parse_invalid_json_is_non_domain_exception() -> None:
    with pytest.raises(ValueError, match="JSON検証"):
        parse_review_response("not-json")
