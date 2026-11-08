from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from bookforge.manifest import load_schema, validate_job

FIXTURES = Path(__file__).parent / "fixtures"


def test_sample_job_is_valid() -> None:
    job = validate_job(FIXTURES / "sample_job.json")
    assert job["version"] == 1
    assert len(job["segments"]) == 1


def test_unsupported_version_is_rejected(tmp_path: Path) -> None:
    job = json.loads((FIXTURES / "sample_job.json").read_text(encoding="utf-8"))
    job["version"] = 2
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValidationError):
        validate_job(path)


def test_schema_is_draft_2020_12() -> None:
    assert load_schema()["$schema"].endswith("2020-12/schema")
