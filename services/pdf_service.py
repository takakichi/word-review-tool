"""PDF page inspection and text extraction."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
# PDF処理はこのサービス内で完結し、UIやLLM通信には依存しません。
# BytesIOはバイト列をファイルのように読み取れる、メモリ上のストリームです。


class PdfProcessingError(RuntimeError):
    """Raised when generated PDF data cannot be processed."""


def get_page_count(pdf_bytes: bytes) -> int:
    """Return the number of pages in an in-memory PDF."""
    try:
        with BytesIO(pdf_bytes) as stream:
            # pagesはページの一覧。lenで総ページ数を取得します。
            return len(PdfReader(stream).pages)
    except Exception as exc:
        raise PdfProcessingError("変換後PDFのページ数を取得できませんでした。") from exc


def validate_page_range(start_page: int, end_page: int, total_pages: int) -> None:
    """Validate an inclusive, one-based page range."""
    # 正常時に値を返すのではなく、不正時にValueErrorを発生させる検証関数です。
    # UI入力だけに頼らずサービス側でも検証するので、単体テストや別UIからも利用できます。
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
        with BytesIO(pdf_bytes) as stream:
            document = PdfReader(stream)
            validate_page_range(start_page, end_page, len(document.pages))
            # 辞書内包表記: {キー: 値 for ...}でページ番号と抽出本文の対応を作ります。
            # UIのページ番号は1始まり、pagesの添字は0始まりなので1を引きます。
            # rangeの終点は含まれないため、終了ページを含めるにはend_page + 1にします。
            # extract_textがNoneを返す場合は空文字に置き換え、stripで前後の空白を除去します。
            pages = {
                page_number: (
                    document.pages[page_number - 1].extract_text() or ""
                ).strip()
                for page_number in range(start_page, end_page + 1)
            }
    except ValueError:
        # 入力範囲のエラーはそのまま呼び出し元へ返します。
        raise
    except Exception as exc:
        raise PdfProcessingError("指定ページのテキスト抽出に失敗しました。") from exc

    if not any(pages.values()):
        # anyは「少なくとも1つ真か」を調べます。全ページが空なら本文をレビューできません。
        raise PdfProcessingError(
            "指定ページに抽出可能なテキストがありません。画像化された文書は対象外です。"
        )
    return pages
