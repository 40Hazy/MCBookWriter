from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .chapters import Chapter
from .normalize import NormalizedText
from .rules import CleanedText
from .segment import Segment


def _non_space_chars(text: str) -> int:
    return sum(1 for char in text if not char.isspace())


def build_report(
    *,
    source_path: str,
    source_hash: str,
    normalized: NormalizedText,
    cleaned: CleanedText,
    chapters: list[Chapter],
    segments: list[Segment],
    title_base: str,
    page_limit: int,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    before_chars = _non_space_chars(normalized.text)
    after_chars = _non_space_chars(cleaned.text)

    if not chapters:
        warnings.append({"level": "error", "code": "no-chapters", "message": "没有识别到任何章节或正文。"})

    if len(title_base) + 3 > 32:
        warnings.append(
            {
                "level": "warning",
                "code": "title-too-long",
                "message": f"书名基名 '{title_base}' 加上序号后可能超过 32 字符。",
            }
        )

    for segment in segments:
        if segment.estimated_pages > page_limit:
            warnings.append(
                {
                    "level": "warning",
                    "code": "segment-over-page-limit",
                    "message": (
                        f"第 {segment.index} 段（{segment.chapter}）估算 {segment.estimated_pages} 页，"
                        f"超过每本 {page_limit} 页上限，模组需要续本。"
                    ),
                }
            )

    removed_total = len(cleaned.removed)
    candidate_lines = cleaned.kept_lines + removed_total
    if candidate_lines and removed_total / candidate_lines > 0.2:
        warnings.append(
            {
                "level": "warning",
                "code": "high-removal-ratio",
                "message": f"删除了 {removed_total}/{candidate_lines} 行（超过 20%），请检查广告规则是否过于激进。",
            }
        )

    if before_chars and after_chars / before_chars < 0.95:
        warnings.append(
            {
                "level": "warning",
                "code": "large-content-loss",
                "message": f"非空白字符从 {before_chars} 降到 {after_chars}，请检查是否误删正文。",
            }
        )

    if normalized.controls_removed:
        warnings.append(
            {
                "level": "info",
                "code": "controls-removed",
                "message": f"移除了 {normalized.controls_removed} 个控制字符。",
            }
        )

    if "§" in cleaned.text:
        warnings.append(
            {
                "level": "info",
                "code": "formatting-codes",
                "message": "文本包含 § 格式码；分页和最终渲染需要实际验证。",
            }
        )

    return {
        "source": {
            "path": source_path,
            "bytes": normalized.original_bytes,
            "encoding": normalized.encoding,
            "had_bom": normalized.had_bom,
            "sha256": source_hash,
        },
        "normalization": {
            "tabs_replaced": normalized.tabs_replaced,
            "controls_removed": normalized.controls_removed,
            "input_lines": cleaned.input_lines,
        },
        "cleaning": {
            "blank_lines_removed": cleaned.blank_lines_removed,
            "kept_lines": cleaned.kept_lines,
            "removed_lines": len(cleaned.removed),
            "removed": [asdict(line) for line in cleaned.removed],
        },
        "text": {
            "non_space_chars_before": before_chars,
            "non_space_chars_after": after_chars,
        },
        "chapters": [
            {
                "index": chapter.index,
                "title": chapter.title,
                "chars": len(chapter.text),
                "start_line": chapter.start_line,
                "end_line": chapter.end_line,
            }
            for chapter in chapters
        ],
        "segments": [
            {
                "index": segment.index,
                "chapter": segment.chapter,
                "chars": segment.char_count,
                "estimated_pages": segment.estimated_pages,
            }
            for segment in segments
        ],
        "summary": {
            "chapters": len(chapters),
            "segments": len(segments),
            "page_limit": page_limit,
            "max_estimated_pages": max((segment.estimated_pages for segment in segments), default=0),
        },
        "warnings": warnings,
    }
