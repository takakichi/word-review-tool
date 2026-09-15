"""Page-aware text formatting and chunking."""

from __future__ import annotations


def format_pages(page_texts: dict[int, str]) -> str:
    """Format page text using unambiguous page markers."""
    # 辞書のitems()から（ページ番号, 本文）を取り出し、ページ見出し付きの本文を作ります。
    return "\n\n".join(
        f"--- PAGE {page} ---\n\n{text}" for page, text in page_texts.items()
    )


def _split_long_text(text: str, limit: int) -> list[str]:
    """Split text by paragraphs, falling back to fixed-size slices."""
    paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
    # このPoCでは、抽出テキストの非空行を段落相当の分割単位として扱います。
    # Wordの段落構造そのものを取得しているわけではありません。
    if not paragraphs:
        return [""]

    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        # 1段落が上限を超えたら、text[開始:終了]のスライスで固定長に分割します。
        candidates = [
            paragraph[index : index + limit]
            for index in range(0, len(paragraph), limit)
        ]
        for candidate in candidates:
            # 小さい段落はまとめ、上限を超える直前で現在のまとまりを確定します。
            joined = f"{current}\n{candidate}".strip() if current else candidate
            if current and len(joined) > limit:
                pieces.append(current)
                current = candidate
            else:
                current = joined
    if current:
        # ループの最後に残った本文も忘れずに追加します。
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
        # ページ見出しと改行も文字数に含まれるので、その分だけ本文の上限を減らします。
        for piece in _split_long_text(text, body_limit):
            blocks.append(f"{marker}\n\n{piece}")
            # 同じページが分割されても各断片にページ番号を付け、原文との対応を保持します。

    chunks: list[str] = []
    current = ""
    for block in blocks:
        # ページブロックを上限まで詰め合わせます。小さいページは同じチャンクに入ります。
        # チャンク上限は本文側の文字数であり、共通のレビュー指示はこの後で追加されます。
        candidate = f"{current}\n\n{block}" if current else block
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
