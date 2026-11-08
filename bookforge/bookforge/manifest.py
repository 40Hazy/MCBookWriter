from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from .segment import Segment

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "job.schema.json"


def _schema_candidates() -> list[Path]:
    candidates = [
        ROOT / "docs" / "job.schema.json",
        Path(__file__).resolve().parents[2] / "docs" / "job.schema.json",
    ]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidates.append(Path(bundle) / "docs" / "job.schema.json")
    return candidates


def load_schema() -> dict[str, Any]:
    for candidate in _schema_candidates():
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"job.schema.json not found: {_schema_candidates()}")


def validate_job_data(job: dict[str, Any]) -> dict[str, Any]:
    validator = Draft202012Validator(load_schema())
    errors = sorted(validator.iter_errors(job), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        raise ValidationError(f"{location}: {first.message}")
    return job


def validate_job(path: str | Path) -> dict[str, Any]:
    job = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_job_data(job)


def build_job(
    *,
    title_base: str,
    page_limit: int,
    source_hash: str,
    segments: list[Segment],
    created_at: str,
) -> dict[str, Any]:
    return {
        "version": 1,
        "titleBase": title_base,
        "pageLimit": page_limit,
        "sourceHash": source_hash,
        "createdAt": created_at,
        "options": {
            "stripFormatting": False,
            "llmApplied": False,
        },
        "segments": [
            {
                "index": segment.index,
                "chapter": segment.chapter,
                "text": segment.text,
            }
            for segment in segments
        ],
    }
