"""Streamlit UI for local Word document review with Ollama."""

from __future__ import annotations

import hashlib
import json
import logging

import streamlit as st

from config.review_rules import DEFAULT_REVIEW_RULES, REVIEW_RULES
from config.settings import SETTINGS
from models.review_models import ReviewRunResult
from services.ollama_service import OllamaClient, OllamaError
from services.pdf_service import (
    PdfProcessingError,
    extract_page_texts,
    get_page_count,
    validate_page_range,
)
from services.prompt_service import build_full_prompt, build_instruction_prompt
from services.review_service import run_review
from services.word_service import WordConversionError, convert_docx_bytes_to_pdf
from utils.file_utils import SEVERITY_LABELS, reviews_to_markdown
from utils.text_utils import chunk_page_texts, format_pages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

st.set_page_config(page_title="Word文書 自動レビュー支援", page_icon="📝", layout="wide")
st.title("Word文書 自動レビュー支援ツール")
st.caption("文書はMicrosoft WordでPDF化し、許可されたOllama API以外には送信しません。")


def _client(base_url: str) -> OllamaClient:
    """Create an Ollama client from UI and environment settings."""
    return OllamaClient(
        base_url=base_url,
        timeout_seconds=SETTINGS.ollama_timeout_seconds,
        allowed_hosts=SETTINGS.ollama_allowed_hosts,
    )


def _clear_document_state() -> None:
    """Drop derived in-memory state when the uploaded file changes."""
    for key in ("document_digest", "pdf_bytes", "total_pages", "review_result", "run_signature"):
        st.session_state.pop(key, None)


left, right = st.columns([1, 1.45], gap="large")

with left:
    st.subheader("設定")
    uploaded = st.file_uploader(
        "Wordファイル",
        type=["docx"],
        help="PDF変換には、このPCにインストールされたMicrosoft Wordを使用します。",
    )

    if uploaded is None:
        _clear_document_state()
    else:
        uploaded_bytes = uploaded.getvalue()
        digest = hashlib.sha256(uploaded_bytes).hexdigest()
        if st.session_state.get("document_digest") != digest:
            _clear_document_state()
            try:
                with st.spinner("Word変換中..."):
                    pdf_bytes = convert_docx_bytes_to_pdf(uploaded_bytes, uploaded.name)
                    total_pages = get_page_count(pdf_bytes)
                st.session_state.document_digest = digest
                st.session_state.pdf_bytes = pdf_bytes
                st.session_state.total_pages = total_pages
            except (WordConversionError, PdfProcessingError) as exc:
                st.error(str(exc))

    total_pages = int(st.session_state.get("total_pages", 0))
    if total_pages:
        st.success(f"PDF変換完了: 全 {total_pages} ページ")

    st.markdown("#### レビュー対象ページ")
    page_col1, page_col2 = st.columns(2)
    with page_col1:
        start_page = st.number_input(
            "開始ページ", min_value=1, max_value=max(1, total_pages), value=1, step=1
        )
    with page_col2:
        end_page = st.number_input(
            "終了ページ",
            min_value=1,
            max_value=max(1, total_pages),
            value=max(1, total_pages),
            step=1,
        )

    st.markdown("#### Ollama設定")
    ollama_url = st.text_input("Ollama API URL", value=SETTINGS.ollama_base_url)
    if st.button("モデル一覧を取得／更新", use_container_width=True):
        try:
            st.session_state.ollama_models = _client(ollama_url).list_models()
            st.session_state.models_url = ollama_url
            if not st.session_state.ollama_models:
                st.warning("インストール済みモデルがありません。`ollama pull <model>`を実行してください。")
        except OllamaError as exc:
            st.session_state.ollama_models = []
            st.error(str(exc))

    models = (
        st.session_state.get("ollama_models", [])
        if st.session_state.get("models_url") == ollama_url
        else []
    )
    if models:
        default_index = models.index(SETTINGS.ollama_model) if SETTINGS.ollama_model in models else 0
        ollama_model = st.selectbox("Ollamaモデル", models, index=default_index)
    else:
        ollama_model = st.text_input(
            "Ollamaモデル",
            value=SETTINGS.ollama_model,
            placeholder="例: qwen3:8b",
            help="一覧を取得できない場合も手入力できます。",
        )

    st.markdown("#### レビュー観点")
    selected_rules = st.multiselect(
        "複数選択できます",
        list(REVIEW_RULES),
        default=list(DEFAULT_REVIEW_RULES),
    )
    other_perspective = st.text_area(
        "その他のレビュー観点", placeholder="独自の確認指示を入力（任意）", height=80
    )
    chunk_size = st.number_input(
        "チャンク上限（文字数）",
        min_value=500,
        max_value=50000,
        value=SETTINGS.review_chunk_size,
        step=500,
    )

page_texts: dict[int, str] = {}
chunks: list[str] = []
instruction_prompt = ""
full_prompts: list[str] = []
preparation_error = ""
current_signature = ""

if total_pages and st.session_state.get("pdf_bytes"):
    try:
        validate_page_range(int(start_page), int(end_page), total_pages)
        page_texts = extract_page_texts(
            st.session_state.pdf_bytes, int(start_page), int(end_page)
        )
        chunks = chunk_page_texts(page_texts, int(chunk_size))
        instruction_prompt = build_instruction_prompt(selected_rules, other_perspective)
        full_prompts = [build_full_prompt(instruction_prompt, chunk) for chunk in chunks]
        current_signature = hashlib.sha256(
            (ollama_url + ollama_model + "\n".join(full_prompts)).encode("utf-8")
        ).hexdigest()
    except (ValueError, PdfProcessingError) as exc:
        preparation_error = str(exc)

with left:
    if preparation_error:
        st.error(preparation_error)
    if instruction_prompt:
        with st.expander("A. レビュー指示プロンプト", expanded=False):
            st.code(instruction_prompt, language="text")
        with st.expander("B. 実際のLLM送信プロンプト", expanded=False):
            st.caption(f"全 {len(full_prompts)} チャンク")
            for index, prompt in enumerate(full_prompts, start=1):
                with st.expander(f"チャンク {index} / {len(full_prompts)}", expanded=False):
                    st.code(prompt, language="text")

    execute = st.button(
        "レビューを実行",
        type="primary",
        use_container_width=True,
        disabled=not bool(full_prompts and ollama_model.strip()),
    )

with right:
    st.subheader("レビュー")
    if page_texts:
        with st.expander("抽出テキスト", expanded=False):
            st.code(format_pages(page_texts), language="text")

    if execute:
        try:
            client = _client(ollama_url)
            progress = st.progress(0, text="レビューを開始します...")
            with st.status("レビュー実行中", expanded=True) as status:

                def show_progress(index: int, total: int) -> None:
                    st.write(f"チャンク {index} / {total} レビュー中")
                    progress.progress((index - 1) / total, text=f"チャンク {index} / {total}")

                result = run_review(
                    client,
                    ollama_model,
                    instruction_prompt,
                    chunks,
                    on_progress=show_progress,
                )
                progress.progress(1.0, text="レビュー完了")
                status.update(label="レビュー完了", state="complete", expanded=False)
            st.session_state.review_result = result.model_dump()
            st.session_state.run_signature = current_signature
        except OllamaError as exc:
            st.error(str(exc))
        except Exception as exc:
            logging.getLogger(__name__).exception("Unexpected review failure (content omitted).")
            st.error(f"レビュー処理で予期しないエラーが発生しました: {type(exc).__name__}")

    result_is_current = bool(
        current_signature
        and st.session_state.get("run_signature") == current_signature
        and st.session_state.get("review_result")
    )
    if result_is_current:
        result = ReviewRunResult.model_validate(st.session_state.review_result)
        st.markdown("### レビュー結果")
        severity_filter = st.multiselect(
            "重要度フィルター",
            ["high", "medium", "low"],
            default=["high", "medium", "low"],
            format_func=lambda value: f"{SEVERITY_LABELS[value]} ({value})",
        )
        visible_reviews = [item for item in result.reviews if item.severity in severity_filter]
        if not visible_reviews:
            st.info("表示条件に該当する指摘はありません。")
        for item in visible_reviews:
            severity_icon = {"high": "🔴", "medium": "🟠", "low": "🔵"}[item.severity]
            with st.container(border=True):
                st.markdown(
                    f"**ページ {item.page}**　{severity_icon} 重要度: "
                    f"{SEVERITY_LABELS[item.severity]}　**観点:** {item.category}"
                )
                st.markdown(f"**対象**  \n> {item.target_text}")
                st.markdown(f"**問題**  \n{item.issue}")
                st.markdown(f"**改善案**  \n{item.suggestion}")

        if result.failures:
            st.warning(f"{len(result.failures)}件のチャンクでJSON解析に失敗しました。")
            for failure in result.failures:
                with st.expander(f"チャンク {failure.chunk_number} の解析エラー"):
                    st.error(failure.error)
                    st.code(failure.raw_response, language="text")

        markdown_report = reviews_to_markdown(result.reviews)
        download_col1, download_col2 = st.columns(2)
        with download_col1:
            st.download_button(
                "Markdownをダウンロード",
                data=markdown_report.encode("utf-8-sig"),
                file_name="review_result.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with download_col2:
            st.download_button(
                "JSONをダウンロード",
                data=json.dumps(
                    [item.model_dump() for item in result.reviews],
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8"),
                file_name="review_result.json",
                mime="application/json",
                use_container_width=True,
            )
    elif st.session_state.get("review_result") and page_texts:
        st.info("設定または対象文書が変更されました。現在の条件でレビューを再実行してください。")
    elif not page_texts:
        st.info("Wordファイルを選択し、対象ページを準備してください。")
