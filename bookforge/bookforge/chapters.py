from __future__ import annotations

import re
from dataclasses import dataclass


NUMBERED_HEADING_RE = re.compile(r"^\s*(\d+)\s*[.．]\s*(.*)$")
DATE_RE = re.compile(r"^\s*\d{4}\s*[.．]\s*\d{1,2}\s*[.．]\s*\d{1,2}\s*$")
CN_HEADING_RE = re.compile(r"^\s*第[零一二三四五六七八九十百千0-9]+[章回节卷]\s*.*$")
MAX_HEADING_LENGTH = 80
MAX_NUMBERED_TITLE_LENGTH = 50


@dataclass(frozen=True)
class Chapter:
    index: int
    title: str
    text: str
    start_line: int
    end_line: int


def _is_heading(line: str) -> tuple[bool, str]:
    stripped = line.strip()
    if not stripped or DATE_RE.fullmatch(stripped):
        return False, ""

    match = NUMBERED_HEADING_RE.match(stripped)
    if match and len(stripped) <= MAX_HEADING_LENGTH:
        number = match.group(1)
        title = match.group(2).strip()
        if len(title) <= MAX_NUMBERED_TITLE_LENGTH:
            return True, f"{number}. {title}".strip() if title else f"第{number}章"

    if len(stripped) <= MAX_HEADING_LENGTH and CN_HEADING_RE.match(stripped):
        return True, stripped

    return False, ""


def parse_chapters(text: str) -> list[Chapter]:
    lines = text.split("\n")
    chapters: list[Chapter] = []
    preamble_lines: list[str] = []
    current_title = ""
    current_start = 0
    current_lines: list[str] = []

    def flush(end_line: int) -> None:
        nonlocal current_title, current_start, current_lines
        if current_title and current_lines:
            chapters.append(
                Chapter(
                    index=len(chapters) + 1,
                    title=current_title,
                    text="\n".join(current_lines).strip("\n"),
                    start_line=current_start,
                    end_line=end_line,
                )
            )
        current_title = ""
        current_start = 0
        current_lines = []

    for line_no, line in enumerate(lines, start=1):
        is_heading, title = _is_heading(line)
        if is_heading:
            if not chapters and not current_title and preamble_lines:
                chapters.append(
                    Chapter(
                        index=1,
                        title="前言",
                        text="\n".join(preamble_lines).strip("\n"),
                        start_line=1,
                        end_line=line_no - 1,
                    )
                )
                preamble_lines = []
            flush(line_no - 1)
            current_title = title
            current_start = line_no
            current_lines = [line.strip()]
            continue

        if current_title:
            if line.strip():
                current_lines.append(line.strip())
        elif line.strip():
            preamble_lines.append(line.strip())

    flush(len(lines))

    if not chapters:
        body = "\n".join(preamble_lines or [line.strip() for line in lines if line.strip()])
        if body:
            chapters.append(
                Chapter(index=1, title="正文", text=body, start_line=1, end_line=len(lines))
            )

    return chapters
