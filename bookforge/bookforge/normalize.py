from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from charset_normalizer import from_bytes


@dataclass(frozen=True)
class NormalizedText:
    text: str
    encoding: str
    had_bom: bool
    tabs_replaced: int
    controls_removed: int
    original_bytes: int


def _pick_charset_match(data: bytes):
    matches = [match for match in from_bytes(data) if match.encoding]
    chinese = [
        match
        for match in matches
        if (match.language or "").lower() in {"chinese", "zh"}
    ]
    if chinese:
        chinese.sort(
            key=lambda match: (
                match.chaos,
                0 if match.encoding in {"gb18030", "gb2312", "gbk"} else 1,
            )
        )
        return chinese[0]

    return from_bytes(data).best()


def decode_bytes(data: bytes) -> tuple[str, str, bool]:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), "utf-8-sig", True
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16"), "utf-16", False

    try:
        return data.decode("utf-8"), "utf-8", False
    except UnicodeDecodeError:
        pass

    best = _pick_charset_match(data)
    if best is not None:
        try:
            return str(best), best.encoding, False
        except (LookupError, UnicodeDecodeError):
            pass

    return data.decode("gb18030"), "gb18030", False


def normalize_text(text: str) -> tuple[str, int, int]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    tabs_replaced = text.count("\t")
    text = text.replace("\t", "    ")

    controls_removed = 0
    kept: list[str] = []
    for char in text:
        codepoint = ord(char)
        if char == "\n":
            kept.append(char)
        elif codepoint < 0x20 or codepoint == 0x7F or char == "\ufeff":
            controls_removed += 1
        else:
            kept.append(char)

    text = unicodedata.normalize("NFC", "".join(kept))
    text = "\n".join(line.rstrip(" \t\u3000") for line in text.split("\n"))
    return text, tabs_replaced, controls_removed


def normalize_bytes(data: bytes) -> NormalizedText:
    text, encoding, had_bom = decode_bytes(data)
    normalized, tabs_replaced, controls_removed = normalize_text(text)
    return NormalizedText(
        text=normalized,
        encoding=encoding,
        had_bom=had_bom,
        tabs_replaced=tabs_replaced,
        controls_removed=controls_removed,
        original_bytes=len(data),
    )


def read_and_normalize(path: str | Path) -> NormalizedText:
    return normalize_bytes(Path(path).read_bytes())
