from utils.text_utils import chunk_page_texts


def test_chunking_prefers_pages_and_preserves_page_markers() -> None:
    chunks = chunk_page_texts({1: "A" * 60, 2: "B" * 60}, max_chars=100)

    assert len(chunks) == 2
    assert chunks[0].startswith("--- PAGE 1 ---")
    assert chunks[1].startswith("--- PAGE 2 ---")


def test_long_page_is_split_and_each_chunk_keeps_page_number() -> None:
    chunks = chunk_page_texts({3: "段落1\n" + "X" * 250}, max_chars=100)

    assert len(chunks) >= 3
    assert all(chunk.startswith("--- PAGE 3 ---") for chunk in chunks)
    assert all(len(chunk) <= 100 for chunk in chunks)

