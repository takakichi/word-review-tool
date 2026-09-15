"""Prompt construction kept separate from the Streamlit UI."""

from __future__ import annotations

from config.review_rules import REVIEW_RULES
# プロンプトは文字列を組み立てるだけの関数にし、画面やAPI接続がなくてもテストできます。


def build_instruction_prompt(
    selected_rules: list[str], other_perspective: str = ""
) -> str:
    """Build the reusable instruction portion without document content."""
    if not selected_rules and not other_perspective.strip():
        raise ValueError("レビュー観点を1つ以上指定してください。")

    unknown = [name for name in selected_rules if name not in REVIEW_RULES]
    # リスト内包表記で、設定辞書にない観点だけを取り出して検証します。
    if unknown:
        raise ValueError(f"未定義のレビュー観点です: {', '.join(unknown)}")

    rule_lines = [f"- {name}: {REVIEW_RULES[name]}" for name in selected_rules]
    # 観点名だけでなく、辞書にある具体的な指示も含めます。f文字列は{}内の値を埋め込みます。
    if other_perspective.strip():
        rule_lines.append(f"- その他: {other_perspective.strip()}")

    # 行のリストを改行で連結して1つの文字列にします。
    # 下の *rule_lines は、リストの中身を展開して各観点の行を挿入する書き方です。
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
    # 共通の指示に1チャンクの本文だけを追加します。
    # 表示用とAPI送信用が同じ関数を使うため、確認画面と実際の送信内容を一致させられます。
    return (
        f"{instruction_prompt}\n\n"
        "# レビュー対象文書\n"
        "以下の本文のみをレビューしてください。\n\n"
        f"{document_chunk}"
    )
