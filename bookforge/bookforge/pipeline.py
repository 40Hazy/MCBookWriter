from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .chapters import parse_chapters
from .manifest import build_job, validate_job_data
from .normalize import normalize_bytes
from .rules import clean_text
from .segment import DEFAULT_MAX_SEGMENT_CHARS, segment_chapters
from .validate import build_report


@dataclass(frozen=True)
class PrepareResult:
    out_dir: Path
    job_path: Path
    report_path: Path
    job: dict
    report: dict


def prepare_document(
    input_path: str | Path,
    out_dir: str | Path,
    *,
    title: str,
    page_limit: int = 100,
    max_segment_chars: int = DEFAULT_MAX_SEGMENT_CHARS,
) -> PrepareResult:
    source = Path(input_path)
    raw = source.read_bytes()
    normalized = normalize_bytes(raw)
    cleaned = clean_text(normalized.text)
    chapters = parse_chapters(cleaned.text)
    segments = segment_chapters(chapters, max_chars=max_segment_chars)

    if not segments:
        raise ValueError("没有可写入的正文内容")

    source_hash = hashlib.sha256(raw).hexdigest()
    report = build_report(
        source_path=str(source.resolve()),
        source_hash=source_hash,
        normalized=normalized,
        cleaned=cleaned,
        chapters=chapters,
        segments=segments,
        title_base=title,
        page_limit=page_limit,
    )
    job = build_job(
        title_base=title,
        page_limit=page_limit,
        source_hash=source_hash,
        segments=segments,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    validate_job_data(job)

    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "01_normalized.txt").write_text(normalized.text, encoding="utf-8")
    (destination / "02_cleaned.txt").write_text(cleaned.text, encoding="utf-8")

    report_path = destination / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    job_path = destination / "job.json"
    job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

    return PrepareResult(out_dir=destination, job_path=job_path, report_path=report_path, job=job, report=report)
