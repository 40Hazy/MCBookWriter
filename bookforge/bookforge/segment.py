from __future__ import annotations

import math
from dataclasses import dataclass

from .chapters import Chapter

DEFAULT_MAX_SEGMENT_CHARS = 12_000
CJK_CHARS_PER_LINE = 12
LINES_PER_PAGE = 14


@dataclass(frozen=True)
class Segment:
    index: int
    chapter: str
    text: str
    char_count: int
    estimated_pages: int


def estimate_pages(text: str) -> int:
    if not text:
        return 0
    newlines = text.count("\n")
    lines = math.ceil(len(text) / CJK_CHARS_PER_LINE) + newlines
    return max(1, math.ceil(lines / LINES_PER_PAGE))


def _split_long_line(line: str, max_chars: int) -> list[str]:
    return [line[i : i + max_chars] for i in range(0, len(line), max_chars)]


def _split_chapter(chapter: Chapter, max_chars: int) -> list[str]:
    if len(chapter.text) <= max_chars:
        return [chapter.text]

    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for line in chapter.text.split("\n"):
        parts = [line] if len(line) <= max_chars else _split_long_line(line, max_chars)
        for part in parts:
            required = len(part) + (1 if current else 0)
            if current and current_length + required > max_chars:
                chunks.append("\n".join(current))
                current = []
                current_length = 0
                required = len(part)
            current.append(part)
            current_length += required

    if current:
        chunks.append("\n".join(current))

    return chunks


def segment_chapters(
    chapters: list[Chapter],
    max_chars: int = DEFAULT_MAX_SEGMENT_CHARS,
) -> list[Segment]:
    segments: list[Segment] = []
    for chapter in chapters:
        for chunk in _split_chapter(chapter, max_chars):
            text = chunk.strip("\n")
            if not text:
                continue
            segments.append(
                Segment(
                    index=len(segments) + 1,
                    chapter=chapter.title,
                    text=text,
                    char_count=len(text),
                    estimated_pages=estimate_pages(text),
                )
            )
    return segments
