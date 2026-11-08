from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from bookforge import __version__
from bookforge.linkage import (
    MIN_AUTOBOOK_VERSION,
    STATUS_SCHEMA_VERSION,
    StatusSnapshot,
    autobook_compat,
    build_job_meta,
    current_job_problem,
    describe_status,
    estimate_plan,
    install_job,
    read_autobook_jars,
    read_status,
)

HASH = "a" * 64


def make_job(
    title: str = "三体1",
    *,
    pages: int = 2,
    page_limit: int = 4,
    llm_applied: bool = False,
) -> dict:
    # 每段 168 字符 => 1 页（12 字符/行、14 行/页）。
    segments = [
        {"index": index + 1, "chapter": f"第 {index + 1} 章", "text": "字" * 168}
        for index in range(pages)
    ]
    return {
        "version": 1,
        "titleBase": title,
        "pageLimit": page_limit,
        "sourceHash": HASH,
        "createdAt": "2026-01-01T00:00:00+00:00",
        "options": {"llmApplied": llm_applied},
        "segments": segments,
    }


def write_job(path: Path, job: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    return path


def test_estimate_plan_counts_pages_and_books() -> None:
    job = make_job(pages=9, page_limit=4)

    assert estimate_plan(job) == (3, 9)


def test_build_job_meta_fields() -> None:
    meta = build_job_meta(make_job(llm_applied=True), reviewed=False)

    assert meta["schema"] == 1
    assert meta["titleBase"] == "三体1"
    assert meta["bookCount"] == 1
    assert meta["totalPages"] == 2
    assert meta["pageLimit"] == 4
    assert meta["reviewed"] is True
    assert meta["llmApplied"] is True
    assert meta["sourceHash"] == HASH
    assert meta["generatorVersion"] == __version__


def test_install_job_writes_job_and_meta(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    job_file = write_job(tmp_path / "reviewed" / "job.json", make_job())

    outcome = install_job(job_file, game_dir)

    assert outcome.destination == game_dir / "autobook" / "jobs" / "三体1.json"
    assert outcome.meta_path == game_dir / "autobook" / "jobs" / "三体1.meta.json"
    assert outcome.backup_path is None
    assert outcome.overwritten is False
    assert outcome.book_count == 1
    assert outcome.total_pages == 2
    assert outcome.reviewed is True  # 父目录名为 reviewed
    meta = json.loads(outcome.meta_path.read_text(encoding="utf-8"))
    assert meta["schema"] == 1
    assert meta["titleBase"] == "三体1"
    assert meta["reviewed"] is True


def test_install_job_keeps_backup_on_overwrite(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()
    first = write_job(tmp_path / "job.json", make_job(pages=2))
    install_job(first, game_dir)
    installed = game_dir / "autobook" / "jobs" / "三体1.json"
    original = installed.read_text(encoding="utf-8")

    second = write_job(tmp_path / "job2.json", make_job(pages=3))
    outcome = install_job(second, game_dir)

    assert outcome.overwritten is True
    assert outcome.backup_path == installed.with_name("三体1.json.bak")
    assert outcome.backup_path.read_text(encoding="utf-8") == original
    assert json.loads(outcome.meta_path.read_text(encoding="utf-8"))["totalPages"] == 3


def test_install_job_rejects_bad_jobs_and_paths(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()

    long_title = write_job(tmp_path / "long.json", make_job(title="书" * 25))
    with pytest.raises(ValueError):
        install_job(long_title, game_dir)

    separator = write_job(tmp_path / "sep.json", make_job(title="a/b"))
    with pytest.raises(ValueError, match="路径分隔符"):
        install_job(separator, game_dir)

    bad_version = write_job(tmp_path / "bad.json", make_job())
    bad_version.write_text(
        json.dumps({**make_job(), "version": 2}, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="校验失败"):
        install_job(bad_version, game_dir)

    with pytest.raises(ValueError, match="游戏目录不存在"):
        install_job(write_job(tmp_path / "ok.json", make_job()), tmp_path / "missing")

    assert not (game_dir / "autobook").exists()


def test_read_status_accepts_known_fields_and_ignores_unknown(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    status_path = game_dir / "autobook" / "status.json"
    status_path.parent.mkdir(parents=True)
    status_path.write_text(
        json.dumps(
            {
                "schema": STATUS_SCHEMA_VERSION,
                "runStatus": "running",
                "currentJob": "三体1",
                "nextIndex": 5,
                "completedBooks": 4,
                "totalBooks": 13,
                "verifiedBooks": 3,
                "reason": "",
                "updatedAt": "2026-01-01T00:00:00+00:00",
                "autoBookVersion": "0.12.0",
                "future": {"ignored": True},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    status = read_status(game_dir)

    assert status is not None
    assert status.schema == STATUS_SCHEMA_VERSION
    assert status.run_status == "running"
    assert status.current_job == "三体1"
    assert status.next_index == 5
    assert status.completed_books == 4
    assert status.total_books == 13
    assert status.verified_books == 3
    assert status.autobook_version == "0.12.0"
    assert "4/13" in describe_status(status)
    assert "校验 3" in describe_status(status)


def test_read_status_degrades_on_missing_corrupt_or_other_schema(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    (game_dir / "autobook").mkdir(parents=True)

    assert read_status(game_dir) is None

    status_path = game_dir / "autobook" / "status.json"
    status_path.write_text("{not json", encoding="utf-8")
    assert read_status(game_dir) is None

    status_path.write_text(json.dumps({"schema": 2, "runStatus": "running"}), encoding="utf-8")
    assert read_status(game_dir) is None


def make_jar(path: Path, version: str, minecraft: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "fabric.mod.json",
            json.dumps({"id": "autobook", "version": version, "depends": {"minecraft": minecraft}}),
        )
    return path


def test_autobook_jar_version_and_compatibility(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    game_dir.mkdir()

    state, message = autobook_compat(game_dir)
    assert state == "missing"
    assert "未检测到" in message

    make_jar(game_dir / "mods" / "autobook-0.11.0-mc1.21.8.jar", "0.11.0", "1.21.8")
    state, message = autobook_compat(game_dir)
    assert state == "old"
    assert MIN_AUTOBOOK_VERSION in message

    make_jar(game_dir / "mods" / "autobook-0.12.0-mc1.21.8.jar", "0.12.0", "1.21.8")
    jars = read_autobook_jars(game_dir)
    assert [(jar.version, jar.minecraft) for jar in jars] == [
        ("0.11.0", "1.21.8"),
        ("0.12.0", "1.21.8"),
    ]
    state, message = autobook_compat(game_dir)
    assert state == "ok"
    assert "0.12.0" in message


def test_current_job_problem_detects_missing_and_bad_version(tmp_path: Path) -> None:
    game_dir = tmp_path / "game"
    jobs_dir = game_dir / "autobook" / "jobs"
    jobs_dir.mkdir(parents=True)
    status = StatusSnapshot(
        schema=1,
        run_status="running",
        current_job="三体1",
        next_index=0,
        completed_books=0,
        total_books=1,
        verified_books=0,
        reason="",
        updated_at="",
        autobook_version="0.12.0",
    )

    assert "不存在" in current_job_problem(status, game_dir)

    (jobs_dir / "三体1.json").write_text(json.dumps({**make_job(), "version": 2}), encoding="utf-8")
    assert "version=2" in current_job_problem(status, game_dir)

    (jobs_dir / "三体1.json").write_text(json.dumps(make_job(), ensure_ascii=False), encoding="utf-8")
    assert current_job_problem(status, game_dir) == ""

    (jobs_dir / "三体1.json").write_text("{broken", encoding="utf-8")
    assert "无法解析" in current_job_problem(status, game_dir)
