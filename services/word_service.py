"""Microsoft Word based DOCX to PDF conversion."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from docx2pdf import convert

LOGGER = logging.getLogger(__name__)


class WordConversionError(RuntimeError):
    """Raised when Microsoft Word cannot convert a DOCX file."""


def convert_docx_bytes_to_pdf(docx_bytes: bytes, original_name: str) -> bytes:
    """Convert uploaded DOCX bytes to PDF bytes using an isolated temp directory."""
    if not docx_bytes:
        raise WordConversionError("Wordファイルが空です。")
    if Path(original_name).suffix.lower() != ".docx":
        raise WordConversionError(".docx形式のファイルを指定してください。")

    com_initialized = False
    try:
        # Streamlit runs scripts on a worker thread. Word COM must be initialized
        # explicitly on that thread before docx2pdf invokes Microsoft Word.
        try:
            import pythoncom

            pythoncom.CoInitialize()
            com_initialized = True
        except ImportError:
            pythoncom = None  # type: ignore[assignment]

        with tempfile.TemporaryDirectory(prefix="word_review_") as temp_dir:
            safe_stem = "uploaded_document"
            docx_path = Path(temp_dir) / f"{safe_stem}.docx"
            pdf_path = Path(temp_dir) / f"{safe_stem}.pdf"
            docx_path.write_bytes(docx_bytes)
            convert(str(docx_path), str(pdf_path))
            if not pdf_path.exists() or pdf_path.stat().st_size == 0:
                raise WordConversionError("PDFが生成されませんでした。")
            return pdf_path.read_bytes()
    except WordConversionError:
        raise
    except Exception as exc:
        LOGGER.exception("DOCX to PDF conversion failed (document content omitted).")
        raise WordConversionError(
            "WordからPDFへの変換に失敗しました。Microsoft Wordのインストール、"
            "ファイルの破損、Wordのダイアログ表示を確認してください。"
        ) from exc
    finally:
        if com_initialized:
            pythoncom.CoUninitialize()

