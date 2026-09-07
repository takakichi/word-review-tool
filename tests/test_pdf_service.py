import pytest

from services.pdf_service import validate_page_range


@pytest.mark.parametrize("start,end,total", [(1, 1, 1), (1, 3, 3), (2, 2, 5)])
def test_validate_page_range_accepts_valid_range(start: int, end: int, total: int) -> None:
    validate_page_range(start, end, total)


@pytest.mark.parametrize("start,end,total", [(0, 1, 1), (1, 4, 3), (3, 2, 3)])
def test_validate_page_range_rejects_invalid_range(start: int, end: int, total: int) -> None:
    with pytest.raises(ValueError):
        validate_page_range(start, end, total)

