from __future__ import annotations

from bookforge.rules import clean_text


def test_removes_ads_and_blank_lines_but_keeps_prose() -> None:
    text = "\n".join(
        [
            "",
            "这是正文第一段。",
            "",
            "请访问 www.example.com 获取更多精彩内容。",
            "http://ads.example.com",
            "“你旁边有电脑吗？打开 http://example.com/manual 看看。”",
            "本书由某某整理，仅供交流。",
            "",
            "这是正文第二段。",
            "123",
            "",
        ]
    )
    result = clean_text(text)
    assert result.text == "这是正文第一段。\n“你旁边有电脑吗？打开 http://example.com/manual 看看。”\n这是正文第二段。"
    assert result.blank_lines_removed == 4
    assert [line.reason for line in result.removed] == ["url-ad", "url-only", "ad-prefix", "page-number"]
