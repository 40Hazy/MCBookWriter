from __future__ import annotations

from bookforge.chapters import parse_chapters


def test_numbered_chapters_and_preamble() -> None:
    text = "\n".join(
        [
            "书名：测试",
            "作者：某人",
            "1. 开始",
            "第一段。",
            "2. 继续",
            "第二段。",
            "4.",
            "第四段。",
        ]
    )
    chapters = parse_chapters(text)
    assert len(chapters) == 4
    assert chapters[0].title == "前言"
    assert chapters[1].title == "1. 开始"
    assert chapters[2].title == "2. 继续"
    assert chapters[3].title == "第4章"


def test_date_lines_are_not_chapters() -> None:
    text = "1. 开始\n正文。\n2024.1.1\n仍属于第一章。"
    chapters = parse_chapters(text)
    assert len(chapters) == 1
    assert "2024.1.1" in chapters[0].text


def test_text_without_headings_becomes_body() -> None:
    chapters = parse_chapters("第一段。\n第二段。")
    assert len(chapters) == 1
    assert chapters[0].title == "正文"
