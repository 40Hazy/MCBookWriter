from __future__ import annotations

from bookforge import __version__
from bookforge.gui.help_content import build_help_html, build_path_info
from bookforge.llm import BOOKFORGE_ROOT, DEFAULT_CONFIG_FILE, DEFAULT_KEY_FILE


def test_help_html_covers_required_sections() -> None:
    page = build_help_html()
    for keyword in (
        "快速开始",
        "支持的输入格式",
        "LLM 核验流程",
        "补丁安全规则",
        "密钥配置",
        "安装到游戏",
        "常见错误",
        "版本与路径信息",
        "游戏联动",
        "联调步骤",
        "/autobook jobs",
        "BOOKFORGE_LLM_KEY_FILE",
        "/autobook add",
        "bookforge key",
    ):
        assert keyword in page, f"帮助页缺少内容: {keyword}"


def test_help_html_is_offline() -> None:
    page = build_help_html()
    # 离线要求：不加载任何外部资源（提及网址文本可以，但不能有外部引用）。
    for tag in ("<img", "<script", "<link", "<iframe", 'href="http', "src=\"http"):
        assert tag not in page, f"帮助页包含外部资源引用: {tag}"


def test_path_info_shows_version_and_paths() -> None:
    info = build_path_info(game_dir="D:\\game")
    assert f"v{__version__}" in info
    assert str(BOOKFORGE_ROOT / "keys") in info
    assert str(DEFAULT_CONFIG_FILE) in info
    assert str(DEFAULT_KEY_FILE) in info
    assert "D:\\game" in info


def test_path_info_escapes_html() -> None:
    info = build_path_info(game_dir='D:\\a<b&"c')
    assert 'D:\\a<b&"c' not in info
    assert "&lt;b&amp;" in info


def test_path_info_without_game_dir() -> None:
    info = build_path_info()
    assert "未设置" in info
