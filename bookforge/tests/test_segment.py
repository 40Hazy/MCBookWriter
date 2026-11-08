from __future__ import annotations

from bookforge.chapters import Chapter
from bookforge.segment import estimate_pages, segment_chapters


def test_long_chapter_is_split_at_paragraph_boundaries() -> None:
    text = "\n".join(f"第{i}段。" + "内容" * 10 for i in range(1, 21))
    chapter = Chapter(index=1, title="1. 测试", text=text, start_line=1, end_line=20)
    segments = segment_chapters([chapter], max_chars=100)
    assert len(segments) > 1
    assert all(segment.char_count <= 100 for segment in segments)
    assert segments[0].text.startswith("第1段")
    assert segments[-1].text.endswith("内容")


def test_estimate_pages_is_at_least_one() -> None:
    assert estimate_pages("短句") == 1
    assert estimate_pages("字" * 2000) > 1
