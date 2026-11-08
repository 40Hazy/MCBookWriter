from __future__ import annotations

from bookforge.normalize import normalize_bytes


def test_bom_crlf_tabs_and_controls() -> None:
    data = b"\xef\xbb\xbfa\r\nb\tc\x00d"
    result = normalize_bytes(data)
    assert result.text == "a\nb    cd"
    assert result.had_bom is True
    assert result.encoding == "utf-8-sig"
    assert result.tabs_replaced == 1
    assert result.controls_removed == 1


def test_gb18030_fallback() -> None:
    result = normalize_bytes("中文测试".encode("gb18030"))
    assert result.text == "中文测试"


def test_trailing_whitespace_is_removed() -> None:
    result = normalize_bytes("第一行   \n第二行\u3000\u3000".encode("utf-8"))
    assert result.text == "第一行\n第二行"
