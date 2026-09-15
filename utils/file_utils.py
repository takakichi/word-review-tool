"""Safe output formatting helpers; uploaded files are handled in memory."""

from __future__ import annotations

from models.review_models import ReviewItem

SEVERITY_LABELS = {"high": "高", "medium": "中", "low": "低"}
# APIで使う重要度の値を、人が読む画面・レポート用の日本語に対応させる辞書です。


def reviews_to_markdown(reviews: list[ReviewItem]) -> str:
    """Render validated review items as a downloadable Markdown report."""
    lines = ["# Word文書レビュー結果", ""]
    # ファイルへ直接書き込まず、Markdown文字列を返します。保存操作はUIのダウンロードが担当します。
    if not reviews:
        return "\n".join(lines + ["指摘事項はありませんでした。", ""])

    for index, item in enumerate(reviews, start=1):
        # enumerateで番号と要素を同時に取り出します。start=1はレポートの番号を1から始める指定です。
        lines.extend(
            # extendは複数の行を追加します。空文字の行はMarkdownの空行になります。
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
    # 最後に行のリストを改行で連結し、ダウンロードできる1つの文字列にします。
