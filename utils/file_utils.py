"""Safe output formatting helpers; uploaded files are handled in memory."""

from __future__ import annotations

from models.review_models import ReviewItem

SEVERITY_LABELS = {"high": "高", "medium": "中", "low": "低"}


def reviews_to_markdown(reviews: list[ReviewItem]) -> str:
    """Render validated review items as a downloadable Markdown report."""
    lines = ["# Word文書レビュー結果", ""]
    if not reviews:
        return "\n".join(lines + ["指摘事項はありませんでした。", ""])

    for index, item in enumerate(reviews, start=1):
        lines.extend(
            [
                f"## {index}. ページ {item.page} — {item.category}",
                "",
                f"- 重要度: {SEVERITY_LABELS[item.severity]} (`{item.severity}`)",
                f"- 対象: 「{item.target_text}」",
                "",
                f"**問題**  \n{item.issue}",
                "",
                f"**改善案**  \n{item.suggestion}",
                "",
            ]
        )
    return "\n".join(lines)

