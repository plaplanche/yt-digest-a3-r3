from yt_digest_node.pages import MARKER, count_words, paginate, truncate


def words(n: int, start: int = 0) -> str:
    return " ".join(f"w{i}" for i in range(start, start + n))


def test_text_within_limit_is_untouched() -> None:
    assert truncate([words(10)], 10) == ([words(10)], False)


def test_truncation_keeps_first_and_last_half() -> None:
    paragraphs, truncated = truncate([words(25)], 10)
    assert truncated
    assert paragraphs == [words(5), MARKER, words(5, 20)]
    assert count_words([p for p in paragraphs if p != MARKER]) == 10


def test_truncation_keeps_paragraph_breaks_inside_kept_words() -> None:
    paragraphs, _ = truncate([words(3), words(10, 3), words(3, 13), words(9, 16)], 10)
    assert paragraphs == [words(3), words(2, 3), MARKER, words(5, 20)]


def test_pages_group_whole_paragraphs() -> None:
    pages = paginate([words(3), words(2, 3), words(4, 5)], 5)
    assert pages == [f"{words(3)}\n\n{words(2, 3)}", words(4, 5)]


def test_long_paragraph_is_cut_and_order_is_kept() -> None:
    paragraphs = [words(2), words(12, 2), words(1, 14)]
    pages = paginate(paragraphs, 5)
    assert all(0 < len(page.split()) <= 5 for page in pages)
    assert " ".join(pages).split() == " ".join(paragraphs).split()
    assert pages == [words(2), words(5, 2), words(5, 7), f"{words(2, 12)}\n\n{words(1, 14)}"]


def test_marker_weighs_no_word() -> None:
    pages = paginate([words(5), MARKER, words(5, 5)], 5)
    assert pages == [f"{words(5)}\n\n{MARKER}", words(5, 5)]
    assert sum(len(p.replace(MARKER, "").split()) for p in pages) == 10
