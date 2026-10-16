"""Truncation and pages (spec 5.5, 5.6)."""

from collections.abc import Sequence

MARKER = "[…]"


def count_words(paragraphs: Sequence[str]) -> int:
    return sum(len(paragraph.split()) for paragraph in paragraphs)


def _take(paragraphs: Sequence[str], count: int) -> list[str]:
    """The paragraphs holding the first `count` words, the last one cut if needed."""
    taken: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        if count <= 0:
            break
        taken.append(" ".join(words[:count]))
        count -= len(words)
    return taken


def truncate(paragraphs: Sequence[str], max_words: int) -> tuple[list[str], bool]:
    """Keep the first and last `max_words // 2` words around a `[…]` paragraph when too long."""
    if count_words(paragraphs) <= max_words:
        return list(paragraphs), False
    half = max_words // 2
    head = _take(paragraphs, half)
    tail = _take_last(paragraphs, half)[::-1]
    return [*head, MARKER, *tail], True


def _take_last(paragraphs: Sequence[str], count: int) -> list[str]:
    """Like `_take` from the end: paragraphs in reverse order, the last one cut at its start."""
    taken: list[str] = []
    for paragraph in reversed(paragraphs):
        words = paragraph.split()
        if count <= 0:
            break
        taken.append(" ".join(words[max(len(words) - count, 0) :]))
        count -= len(words)
    return taken


def paginate(paragraphs: Sequence[str], page_words: int) -> list[str]:
    """Group whole paragraphs into pages of at most `page_words` words; cut longer paragraphs.

    The `[…]` marker weighs no word.
    """
    pages: list[str] = []
    current: list[str] = []
    size = 0

    def flush() -> None:
        nonlocal current, size
        if current:
            pages.append("\n\n".join(current))
        current, size = [], 0

    for paragraph in paragraphs:
        weight = 0 if paragraph == MARKER else len(paragraph.split())
        if size + weight > page_words:
            flush()
        if weight > page_words:
            words = paragraph.split()
            for start in range(0, len(words) - page_words, page_words):
                pages.append(" ".join(words[start : start + page_words]))
            paragraph = " ".join(words[(len(words) - 1) // page_words * page_words :])
            weight = len(paragraph.split())
        current.append(paragraph)
        size += weight
    flush()
    return pages
