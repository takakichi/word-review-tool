import pytest

from services.review_service import parse_review_response


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

