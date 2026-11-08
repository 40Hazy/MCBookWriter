from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RemovedLine:
    line_no: int
    text: str
    reason: str


@dataclass(frozen=True)
class CleanedText:
    text: str
    removed: tuple[RemovedLine, ...]
    blank_lines_removed: int
    kept_lines: int
    input_lines: int


URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
QUOTE_RE = re.compile(r"[“”\"'「」『』]")
PAGE_NUMBER_RE = re.compile(r"^\s*[-—]?\s*\d{1,4}\s*[-—]?\s*$")

STRONG_AD_PREFIXES = (
    "请记住",
    "最新网址",
    "本站",
    "本书由",
    "手机版",
    "手机阅读",
    "加入书架",
    "推荐阅读",
    "全文阅读",
    "TXT下载",
    "电子书下载",
    "免费阅读",
    "更多精彩",
    "本章完",
    "本章未完",
    "请点击",
    "下一页",
    "求收藏",
    "求推荐",
    "求月票",
    "投推荐票",
    "打赏",
    "订阅",
    "公众号",
    "QQ群",
    "微信群",
    "书友群",
    "交流群",
    "版权声明",
    "免责声明",
    "广告合作",
    "http://",
    "https://",
    "www.",
)

AD_CONTAINS = (
    "公众号",
    "QQ群",
    "书友群",
    "交流群",
    "请关注",
    "请收藏",
    "请推荐",
    "求月票",
    "求打赏",
    "最新章节",
    "全文阅读",
    "手机阅读",
    "免费阅读",
    "TXT下载",
    "电子书",
    "小说网",
    "本站",
    "首发",
    "转自",
    "侵删",
    "广告合作",
    "更多精彩",
    "仅供交流",
    "仅供学习",
    "请勿用于商业",
)

URL_AD_WORDS = (
    "网址",
    "访问",
    "下载",
    "阅读",
    "更多",
    "最新",
    "本章",
    "手机",
    "免费",
)


def classify_ad_line(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None

    if PAGE_NUMBER_RE.fullmatch(stripped):
        return "page-number"

    if QUOTE_RE.search(stripped) and not stripped.startswith(("http://", "https://", "www.")):
        return None

    bare = stripped.strip("。．.!！?？,，、;；:：()（）[]【】")
    if URL_RE.fullmatch(bare):
        return "url-only"

    if stripped.startswith(STRONG_AD_PREFIXES):
        return "ad-prefix"

    if len(stripped) <= 80 and URL_RE.search(stripped) and any(word in stripped for word in URL_AD_WORDS):
        return "url-ad"

    if len(stripped) <= 60 and any(word in stripped for word in AD_CONTAINS):
        return "ad-keyword"

    return None


def clean_text(text: str) -> CleanedText:
    removed: list[RemovedLine] = []
    kept: list[str] = []
    blank_lines_removed = 0
    lines = text.split("\n")

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            blank_lines_removed += 1
            continue

        reason = classify_ad_line(stripped)
        if reason is not None:
            removed.append(RemovedLine(line_no=line_no, text=stripped, reason=reason))
            continue

        kept.append(stripped)

    return CleanedText(
        text="\n".join(kept),
        removed=tuple(removed),
        blank_lines_removed=blank_lines_removed,
        kept_lines=len(kept),
        input_lines=len(lines),
    )
