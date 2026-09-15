"""Exercise partial-result and retry UI without Word or an Ollama server."""
# 画面操作のテスト。実際のWordやLLMの代わりに、モック（テスト用の代用品）を使います。

from pathlib import Path
from unittest.mock import Mock

import streamlit as st
from streamlit.testing.v1 import AppTest

from services import pdf_service, word_service
from services.ollama_service import OllamaClient, OllamaError


def test_partial_result_retry_and_timeout_change(monkeypatch) -> None:
    # 準備: monkeypatchで外部処理を差し替えます。差し替えはテスト終了時に元へ戻ります。
    upload = Mock(name="upload")
    upload.name = "example.docx"
    upload.getvalue.return_value = b"fake docx"
    monkeypatch.setattr(st, "file_uploader", Mock(return_value=upload))
    monkeypatch.setattr(word_service, "convert_docx_bytes_to_pdf", Mock(return_value=b"fake pdf"))
    monkeypatch.setattr(pdf_service, "get_page_count", Mock(return_value=3))
    monkeypatch.setattr(pdf_service, "extract_page_texts", Mock(return_value={1: "A" * 300, 2: "B" * 300, 3: "C" * 300}))
    generate = Mock(side_effect=['{"reviews":[]}', OllamaError("timeout"), '{"reviews":[]}'])
    # side_effectのリストは、呼び出すたびに順に値を返す（例外なら発生させる）設定です。
    monkeypatch.setattr(OllamaClient, "generate", generate)

    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
    # 実行: AppTestでブラウザを開かずに入力欄やボタンを操作します。runで画面を再実行します。
    app.run()
    next(item for item in app.text_input if item.label == "Ollamaモデル").set_value("model")
    next(item for item in app.number_input if item.label == "チャンク上限（文字数）").set_value(500)
    app.run()
    next(item for item in app.button if item.label == "レビューを実行").click()
    app.run()
    assert not app.exception
    # 検証: assertの条件がFalseになるとpytestはテスト失敗として報告します。
    assert len(app.session_state["review_result"]["chunk_results"]) == 3
    assert app.session_state["review_result"]["failures"][0]["chunk_number"] == 2

    next(item for item in app.number_input if item.label == "応答待ち時間（秒）").set_value(900)
    app.run()
    retry_button = next(item for item in app.button if item.label == "選択した失敗チャンクだけ再実行")
    assert not retry_button.disabled
    generate.side_effect = None
    # 再試行では成功応答を返すように変え、失敗した1チャンクだけが再送されたか確認します。
    generate.return_value = '{"reviews":[]}'
    retry_button.click()
    app.run()
    assert not app.exception
    assert app.session_state["review_result"]["failures"] == []
    assert generate.call_count == 4
