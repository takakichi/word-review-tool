"""Microsoft Word based DOCX to PDF conversion."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from docx2pdf import convert

LOGGER = logging.getLogger(__name__)
# __name__はこのモジュールの名前です。ログに処理の発生元を付けるために使います。


class WordConversionError(RuntimeError):
    """Raised when Microsoft Word cannot convert a DOCX file."""


def convert_docx_bytes_to_pdf(docx_bytes: bytes, original_name: str) -> bytes:
    """Convert uploaded DOCX bytes to PDF bytes using an isolated temp directory."""
    # bytesはファイルの中身を表すバイト列。UIから受け取った内容をまず検証します。
    if not docx_bytes:
        raise WordConversionError("Wordファイルが空です。")
    if Path(original_name).suffix.lower() != ".docx":
        raise WordConversionError(".docx形式のファイルを指定してください。")

    com_initialized = False
    # COMはPythonからWindowsアプリ（ここではWord）を操作するための仕組みです。
    # 使用するスレッド上で初期化し、最後に同じスレッドで解放します。
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
            # withを抜けると一時ディレクトリを削除します。例外で抜ける場合も同様です。
            # アップロードされた名前をパスに使わず、固定名で一時領域内に保存します。
            safe_stem = "uploaded_document"
            docx_path = Path(temp_dir) / f"{safe_stem}.docx"
            pdf_path = Path(temp_dir) / f"{safe_stem}.pdf"
            docx_path.write_bytes(docx_bytes)
            # docx2pdfはMicrosoft Wordを操作してPDF化します。Pythonだけで変換するわけではありません。
            convert(str(docx_path), str(pdf_path))
            if not pdf_path.exists() or pdf_path.stat().st_size == 0:
                raise WordConversionError("PDFが生成されませんでした。")
            return pdf_path.read_bytes()
            # returnの値を読んだ後にwithの終了処理が実行されます。
            # 呼び出し元にはPDFの内容だけが返り、一時パスは返しません。
    except WordConversionError:
        raise
    except Exception as exc:
        # 開発者向けログと利用者向けメッセージを分離。文書本文はログに含めません。
        # raise ... from excは、元の例外を原因として残しつつ、専用の例外へ包み直します。
        LOGGER.exception("DOCX to PDF conversion failed (document content omitted).")
        raise WordConversionError(
            "WordからPDFへの変換に失敗しました。Microsoft Wordのインストール、"
            "ファイルの破損、Wordのダイアログ表示を確認してください。"
        ) from exc
    finally:
        # finallyは正常・異常どちらの場合も実行されます。初期化済みの場合だけCOMを解放します。
        if com_initialized:
            pythoncom.CoUninitialize()
