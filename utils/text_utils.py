"""Page-aware text formatting and chunking."""

from __future__ import annotations


def format_pages(page_texts: dict[int, str]) -> str:
    """Format page text using unambiguous page markers."""
    return "\n\n".join(
        f"--- PAGE {page} ---\n\n{text}" for page, text in page_texts.items()
    )


def _split_long_text(text: str, limit: int) -> list[str]:
    """Split text by paragraphs, falling back to fixed-size slices."""
    paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
    if not paragraphs:
        return [""]

    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidates = [
            paragraph[index : index + limit]
            for index in range(0, len(paragraph), limit)
        ]
        for candidate in candidates:
            joined = f"{current}\n{candidate}".strip() if current else candidate
            if current and len(joined) > limit:
                pieces.append(current)
                current = candidate
            else:
                current = joined
    if current:
        pieces.append(current)
    return pieces


def chunk_page_texts(page_texts: dict[int, str], max_chars: int) -> list[str]:
    """Split text page-first, then paragraph/fixed-size, preserving page markers."""
    if max_chars < 100:
        raise ValueError("チャンクサイズは100文字以上にしてください。")

    blocks: list[str] = []
    for page, text in page_texts.items():
        marker = f"--- PAGE {page} ---"
        body_limit = max(1, max_chars - len(marker) - 2)
        for piece in _split_long_text(text, body_limit):
            blocks.append(f"{marker}\n\n{piece}")

    chunks: list[str] = []
    current = ""
    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks

