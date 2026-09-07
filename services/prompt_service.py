"""Prompt construction kept separate from the Streamlit UI."""

from __future__ import annotations

from config.review_rules import REVIEW_RULES


def build_instruction_prompt(
    selected_rules: list[str], other_perspective: str = ""
) -> str:
    """Build the reusable instruction portion without document content."""
    if not selected_rules and not other_perspective.strip():
        raise ValueError("レビュー観点を1つ以上指定してください。")

    unknown = [name for name in selected_rules if name not in REVIEW_RULES]
    if unknown:
        raise ValueError(f"未定義のレビュー観点です: {', '.join(unknown)}")

    rule_lines = [f"- {name}: {REVIEW_RULES[name]}" for name in selected_rules]
    if other_perspective.strip():
        rule_lines.append(f"- その他: {other_perspective.strip()}")

    return "\n".join(
        [
            "# 役割",
            "あなたはシステム要件・設計文書を精査するテクニカルレビュアーです。",
            "",
            "# レビュー目的",
            "指定された観点に基づき、実装・運用・テストで問題になり得る記述を特定し、具体的な改善案を示してください。",
            "文書に根拠がない事実を補わず、指摘がない場合は空のreviews配列を返してください。",
            "",
            "# レビュー観点",
            *rule_lines,
            "",
            "# 出力ルール",
            "JSONオブジェクトだけを出力し、Markdownコードフェンスや前後の説明は付けないでください。",
            '形式: {"reviews":[{"page":1,"category":"観点名","severity":"high|medium|low",',
            '"target_text":"原文の短い引用","issue":"問題の説明","suggestion":"具体的な改善案"}]}',
            "pageは本文の--- PAGE N ---にある実ページ番号を使用してください。",
            "severityは high=仕様誤り・矛盾・重大な記載漏れ、medium=曖昧さ・説明不足・誤解の可能性、",
            "low=表現改善・軽微な不統一、とします。",
            "target_textには該当箇所の原文を短く正確に引用してください。",
        ]
    )


def build_full_prompt(instruction_prompt: str, document_chunk: str) -> str:
    """Append one page-aware document chunk to the instruction prompt."""
    if not document_chunk.strip():
        raise ValueError("レビュー対象本文が空です。")
    return (
        f"{instruction_prompt}\n\n"
        "# レビュー対象文書\n"
        "以下の本文のみをレビューしてください。\n\n"
        f"{document_chunk}"
    )

