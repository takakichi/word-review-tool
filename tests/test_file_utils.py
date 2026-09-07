from models.review_models import ReviewItem
from utils.file_utils import reviews_to_markdown


def test_reviews_to_markdown() -> None:
    item = ReviewItem(
        page=2,
        category="テスト可能性",
        severity="high",
        target_text="正常に動作すること",
        issue="判定条件がない",
        suggestion="期待値を明記する",
    )
    markdown = reviews_to_markdown([item])

    assert "ページ 2" in markdown
    assert "重要度: 高" in markdown
    assert "期待値を明記する" in markdown

