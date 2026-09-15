"""Exercise partial-result and retry UI without Word or an Ollama server."""

from pathlib import Path
from unittest.mock import Mock

import streamlit as st
from streamlit.testing.v1 import AppTest

from services import pdf_service, word_service
from services.ollama_service import OllamaClient, OllamaError


def test_partial_result_retry_and_timeout_change(monkeypatch) -> None:
    upload = Mock(name="upload")
    upload.name = "example.docx"
    upload.getvalue.return_value = b"fake docx"
    monkeypatch.setattr(st, "file_uploader", Mock(return_value=upload))
    monkeypatch.setattr(word_service, "convert_docx_bytes_to_pdf", Mock(return_value=b"fake pdf"))
    monkeypatch.setattr(pdf_service, "get_page_count", Mock(return_value=3))
    monkeypatch.setattr(pdf_service, "extract_page_texts", Mock(return_value={1: "A" * 300, 2: "B" * 300, 3: "C" * 300}))
    generate = Mock(side_effect=['{"reviews":[]}', OllamaError("timeout"), '{"reviews":[]}'])
    monkeypatch.setattr(OllamaClient, "generate", generate)

    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
    app.run()
    next(item for item in app.text_input if item.label == "Ollamaモデル").set_value("model")
    next(item for item in app.number_input if item.label == "チャンク上限（文字数）").set_value(500)
    app.run()
    next(item for item in app.button if item.label == "レビューを実行").click()
    app.run()
    assert not app.exception
    assert len(app.session_state["review_result"]["chunk_results"]) == 3
    assert app.session_state["review_result"]["failures"][0]["chunk_number"] == 2

    next(item for item in app.number_input if item.label == "応答待ち時間（秒）").set_value(900)
    app.run()
    retry_button = next(item for item in app.button if item.label == "選択した失敗チャンクだけ再実行")
    assert not retry_button.disabled
    generate.side_effect = None
    generate.return_value = '{"reviews":[]}'
    retry_button.click()
    app.run()
    assert not app.exception
    assert app.session_state["review_result"]["failures"] == []
    assert generate.call_count == 4
