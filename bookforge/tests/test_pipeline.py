from __future__ import annotations

from pathlib import Path

from bookforge.manifest import validate_job
from bookforge.pipeline import prepare_document

FIXTURES = Path(__file__).parent / "fixtures"


def test_prepare_generates_valid_job_and_report(tmp_path: Path) -> None:
    result = prepare_document(
        FIXTURES / "sample.txt",
        tmp_path,
        title="样例",
        page_limit=100,
        max_segment_chars=12_000,
    )
    assert result.job_path.exists()
    assert result.report_path.exists()
    assert (tmp_path / "01_normalized.txt").exists()
    assert (tmp_path / "02_cleaned.txt").exists()

    job = validate_job(result.job_path)
    assert job["titleBase"] == "样例"
    assert len(job["segments"]) == 1
    assert result.report["summary"]["chapters"] == 1
    assert result.report["summary"]["segments"] == 1


def test_prepare_rejects_empty_input(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("\n\n", encoding="utf-8")
    try:
        prepare_document(empty, tmp_path / "out", title="空")
    except ValueError as error:
        assert "正文" in str(error)
    else:
        raise AssertionError("empty input should fail")
