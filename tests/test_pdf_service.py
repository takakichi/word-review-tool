from io import BytesIO
# このテストは小さなPDFをメモリ上で生成し、ページ数と抽出処理を実際に検証します。
# Word変換やLLM通信を必要としないので、PDFサービスだけを独立して学べます。

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from services.pdf_service import (
    PdfProcessingError,
    extract_page_texts,
    get_page_count,
    validate_page_range,
)


def _make_pdf(texts: list[str]) -> bytes:
    """Build a small in-memory text PDF without Word or other PDF libraries."""
    writer = PdfWriter()
    # テスト用の英字テキストを各ページへ配置します。日本語文書の抽出品質テストではありません。
    for text in texts:
        page = writer.add_blank_page(width=300, height=300)
        page[NameObject("/Resources")] = DictionaryObject(
            # PDF内部のフォント定義。NameObject/DictionaryObjectはPDFの構造を表す型です。
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): DictionaryObject(
                            {
                                NameObject("/Type"): NameObject("/Font"),
                                NameObject("/Subtype"): NameObject("/Type1"),
                                NameObject("/BaseFont"): NameObject("/Helvetica"),
                            }
                        )
                    }
                )
            }
        )
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 12 Tf 20 250 Td ({text}) Tj ET".encode("ascii"))
        # BT～ETはPDFのテキスト描画命令。作った命令をページのContentsへ入れます。
        page[NameObject("/Contents")] = content
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_get_page_count() -> None:
    assert get_page_count(_make_pdf(["First", "Second", "Third"])) == 3


def test_extract_only_selected_pages_with_original_page_numbers() -> None:
    pdf = _make_pdf(["First", "Second", "Third"])
    assert extract_page_texts(pdf, 2, 3) == {2: "Second", 3: "Third"}


def test_extract_blank_page_reports_no_text() -> None:
    with pytest.raises(PdfProcessingError, match="テキストがありません"):
        extract_page_texts(_make_pdf([""]), 1, 1)


# parametrizeは1つのテストを複数の入力で実行するpytestの仕組みです。
@pytest.mark.parametrize("operation", [get_page_count, lambda data: extract_page_texts(data, 1, 1)])
def test_invalid_pdf_is_wrapped_as_processing_error(operation) -> None:
    with pytest.raises(PdfProcessingError):
        # raisesは指定した例外が発生することを検証します。発生しない場合もテスト失敗です。
        operation(b"not a PDF")


@pytest.mark.parametrize("start,end,total", [(1, 1, 1), (1, 3, 3), (2, 2, 5)])
def test_validate_page_range_accepts_valid_range(start: int, end: int, total: int) -> None:
    validate_page_range(start, end, total)


@pytest.mark.parametrize("start,end,total", [(0, 1, 1), (1, 4, 3), (3, 2, 3)])
def test_validate_page_range_rejects_invalid_range(start: int, end: int, total: int) -> None:
    with pytest.raises(ValueError):
        validate_page_range(start, end, total)
