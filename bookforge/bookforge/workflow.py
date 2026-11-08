from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .ebook import ImportedBook, extract_ebook, is_ebook
from .pipeline import PrepareResult, prepare_document
from .segment import DEFAULT_MAX_SEGMENT_CHARS

MAX_TITLE_CHARS = 24


@dataclass(frozen=True)
class PrepareOutcome:
    source: Path
    out_dir: Path
    title: str
    imported: ImportedBook | None
    imported_text_path: Path | None
    import_report_path: Path | None
    result: PrepareResult


def _write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def prepare_input(
    input_path: str | Path,
    out_dir: str | Path,
    *,
    title: str | None = None,
    page_limit: int = 100,
    max_segment_chars: int = DEFAULT_MAX_SEGMENT_CHARS,
    calibre: str | None = None,
) -> PrepareOutcome:
    source = Path(input_path)
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)

    imported: ImportedBook | None = None
    imported_text_path: Path | None = None
    import_report_path: Path | None = None
    prepared_path = source

    if is_ebook(source):
        imported = extract_ebook(source, calibre=calibre)
        imported_text_path = output / "00_imported.txt"
        imported_text_path.write_text(imported.text + "\n", encoding="utf-8")
        import_report_path = output / "import.json"
        _write_json(
            import_report_path,
            {
                "version": 1,
                "format": imported.format,
                "source": str(source),
                "sourceHash": hashlib.sha256(source.read_bytes()).hexdigest(),
                "title": imported.title,
                "author": imported.author,
                "textPath": imported_text_path.name,
                "textChars": len(imported.text),
                "warnings": imported.warnings,
            },
        )
        prepared_path = imported_text_path

    resolved_title = (title or "").strip()
    if imported is not None:
        resolved_title = resolved_title or imported.title.strip() or source.stem
    else:
        resolved_title = resolved_title or source.stem
    if not resolved_title:
        raise ValueError("缺少书名，请用 --title 指定")
    if len(resolved_title) > MAX_TITLE_CHARS:
        raise ValueError(
            f"书名 {resolved_title!r} 有 {len(resolved_title)} 字符，"
            f"超过 job schema 的 {MAX_TITLE_CHARS} 字符限制；"
            "请用 --title 指定更短的书名（AutoBook 还会追加 -NN）"
        )

    result = prepare_document(
        prepared_path,
        output,
        title=resolved_title,
        page_limit=page_limit,
        max_segment_chars=max_segment_chars,
    )
    return PrepareOutcome(
        source=source,
        out_dir=output,
        title=resolved_title,
        imported=imported,
        imported_text_path=imported_text_path,
        import_report_path=import_report_path,
        result=result,
    )
