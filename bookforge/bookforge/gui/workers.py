from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from ..llm import review_job, write_report
from ..manifest import validate_job_data
from ..patch import apply_patches, build_unified_diff
from ..workflow import prepare_input
from .settings import test_connection


class PrepareWorker(QThread):
    log = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        input_path: Path,
        out_dir: Path,
        title: str,
        page_limit: int,
        max_segment_chars: int,
        calibre: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.input_path = input_path
        self.out_dir = out_dir
        self.title = title
        self.page_limit = page_limit
        self.max_segment_chars = max_segment_chars
        self.calibre = calibre

    def run(self) -> None:
        try:
            outcome = prepare_input(
                self.input_path,
                self.out_dir,
                title=self.title or None,
                page_limit=self.page_limit,
                max_segment_chars=self.max_segment_chars,
                calibre=self.calibre,
            )
            if outcome.imported is not None:
                for warning in outcome.imported.warnings:
                    self.log.emit(f"[import] {warning}")
            self.succeeded.emit(outcome)
        except Exception as error:
            self.failed.emit(str(error))


class ReviewWorker(QThread):
    log = Signal(str)
    progress = Signal(int, int, str)
    succeeded = Signal(object, str)
    failed = Signal(str)

    def __init__(
        self,
        job: dict[str, Any],
        job_path: Path,
        settings,
        mode: str,
        sample_chunks: int,
        out_path: Path,
        glossary: list[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.job = job
        self.job_path = job_path
        self.settings = settings
        self.mode = mode
        self.sample_chunks = sample_chunks
        self.out_path = out_path
        self.glossary = glossary
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            self.log.emit(
                f"开始 {self.mode} 核验：profile={self.settings.profile_name or '-'} "
                f"model={self.settings.model}"
            )
            report = review_job(
                self.job,
                self.settings,
                job_path=self.job_path,
                sample_chunks=max(self.sample_chunks, 0),
                mode=self.mode,
                glossary=self.glossary,
                progress=lambda done, total, message: self.progress.emit(
                    done, total, message
                ),
                cancel=self._cancel,
            )
            written = write_report(report, self.out_path)
            self.succeeded.emit(report, str(written))
        except Exception as error:
            self.failed.emit(str(error))


class ApplyWorker(QThread):
    log = Signal(str)
    succeeded = Signal(object, str, str)
    failed = Signal(str)

    def __init__(
        self,
        job: dict[str, Any],
        job_path: Path,
        patch_path: Path,
        issues: list[dict[str, Any]],
        out_dir: Path,
        min_confidence: str,
        max_delta: dict[str, int] | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.job = job
        self.job_path = job_path
        self.patch_path = patch_path
        self.issues = issues
        self.out_dir = out_dir
        self.min_confidence = min_confidence
        self.max_delta = max_delta

    def run(self) -> None:
        try:
            result = apply_patches(
                self.job,
                self.issues,
                min_confidence=self.min_confidence,
                max_delta=self.max_delta,
            )
            validate_job_data(result.job)
            diff_text = build_unified_diff(self.job, result.job)
            summary = {
                "applied": result.applied_count,
                "rejected": result.rejected_count,
                "segmentsChanged": result.segments_changed,
                "diffLines": len(diff_text.splitlines()),
            }
            self.out_dir.mkdir(parents=True, exist_ok=True)
            job_path = self.out_dir / "job.json"
            job_path.write_text(
                json.dumps(result.job, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            reviewed_text = "\n\n".join(
                str(segment.get("text", ""))
                for segment in result.job.get("segments", [])
            )
            (self.out_dir / "03_reviewed.txt").write_text(
                reviewed_text,
                encoding="utf-8",
            )
            (self.out_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
            apply_report = {
                "version": 1,
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "source": {
                    "job": str(self.job_path),
                    "patch": str(self.patch_path),
                    "minConfidence": self.min_confidence,
                    "maxDelta": self.max_delta or {},
                    "diff": "diff.patch",
                },
                "summary": summary,
                "applied": result.applied,
                "rejected": result.rejected,
            }
            apply_path = write_report(apply_report, self.out_dir / "patch_apply.json")
            self.succeeded.emit(result, diff_text, str(apply_path))
        except Exception as error:
            self.failed.emit(str(error))


class ConnectionWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings

    def run(self) -> None:
        try:
            self.succeeded.emit(test_connection(self.settings))
        except Exception as error:
            self.failed.emit(str(error))
