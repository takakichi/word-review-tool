from services.prompt_service import build_full_prompt, build_instruction_prompt


def test_build_instruction_prompt_includes_selected_rule_but_not_document() -> None:
    prompt = build_instruction_prompt(["曖昧な表現"], "法令適合性を確認する")

    assert "判断基準が読み手によって異なる" in prompt
    assert "法令適合性を確認する" in prompt
    assert "レビュー対象文書" not in prompt


def test_build_full_prompt_adds_document() -> None:
    full_prompt = build_full_prompt("instruction", "--- PAGE 2 ---\n本文")
    assert "instruction" in full_prompt
    assert "--- PAGE 2 ---" in full_prompt

