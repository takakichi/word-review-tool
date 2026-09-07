"""PDF page inspection and text extraction."""

from __future__ import annotations

import fitz


class PdfProcessingError(RuntimeError):
    """Raised when generated PDF data cannot be processed."""


def get_page_count(pdf_bytes: bytes) -> int:
    """Return the number of pages in an in-memory PDF."""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            return document.page_count
    except Exception as exc:
        raise PdfProcessingError("変換後PDFのページ数を取得できませんでした。") from exc


def validate_page_range(start_page: int, end_page: int, total_pages: int) -> None:
    """Validate an inclusive, one-based page range."""
    if total_pages < 1:
        raise ValueError("文書にページがありません。")
    if start_page < 1:
        raise ValueError("開始ページは1以上にしてください。")
    if end_page > total_pages:
        raise ValueError(f"終了ページは総ページ数（{total_pages}）以下にしてください。")
    if start_page > end_page:
        raise ValueError("開始ページは終了ページ以下にしてください。")


def extract_page_texts(
    pdf_bytes: bytes, start_page: int, end_page: int
) -> dict[int, str]:
    """Extract text for an inclusive one-based range while retaining page numbers."""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            validate_page_range(start_page, end_page, document.page_count)
            pages = {
                page_number: document.load_page(page_number - 1).get_text("text").strip()
                for page_number in range(start_page, end_page + 1)
            }
    except ValueError:
        raise
    except Exception as exc:
        raise PdfProcessingError("指定ページのテキスト抽出に失敗しました。") from exc

    if not any(pages.values()):
        raise PdfProcessingError(
            "指定ページに抽出可能なテキストがありません。画像化された文書は対象外です。"
        )
    return pages

