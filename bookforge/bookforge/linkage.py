from __future__ import annotations

import json
import math
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .manifest import validate_job_data
from .segment import estimate_pages

# P7.4 文件契约版本：meta.json 与 status.json 各自独立，均为 v1。
META_SCHEMA_VERSION = 1
STATUS_SCHEMA_VERSION = 1
# 支持 meta.json / status.json 联动的最低 AutoBook 版本。
MIN_AUTOBOOK_VERSION = "0.12.0"

MAX_TITLE_CHARS = 24
MAX_BOOK_TITLE_CHARS = 32

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass(frozen=True)
class InstallOutcome:
    destination: Path
    meta_path: Path
    backup_path: Path | None
    book_count: int
    total_pages: int
    overwritten: bool
    reviewed: bool
    llm_applied: bool


@dataclass(frozen=True)
class StatusSnapshot:
    schema: int
    run_status: str
    current_job: str
    next_index: int
    completed_books: int
    total_books: int
    verified_books: int
    reason: str
    updated_at: str
    autobook_version: str


@dataclass(frozen=True)
class JarInfo:
    path: Path
    version: str
    minecraft: str


def effective_page_limit(job: dict[str, Any]) -> int:
    options = job.get("options")
    value: Any = None
    if isinstance(options, dict):
        value = options.get("pageLimit")
    if value is None:
        value = job.get("pageLimit")
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return 100
    return min(max(limit, 1), 100)


def estimate_plan(job: dict[str, Any]) -> tuple[int, int]:
    """按 BookForge 的字符估算得到 (书数, 总页数)，作为安装元数据。"""
    segments = job.get("segments")
    total_pages = 0
    if isinstance(segments, list):
        for segment in segments:
            if isinstance(segment, dict):
                total_pages += estimate_pages(str(segment.get("text", "") or ""))
    limit = effective_page_limit(job)
    book_count = math.ceil(total_pages / limit) if total_pages else 0
    return book_count, total_pages


def _option_flag(job: dict[str, Any], key: str) -> bool:
    options = job.get("options")
    return bool(options.get(key)) if isinstance(options, dict) else False


def build_job_meta(
    job: dict[str, Any],
    *,
    reviewed: bool,
    generated_at: str | None = None,
) -> dict[str, Any]:
    book_count, total_pages = estimate_plan(job)
    llm_applied = _option_flag(job, "llmApplied")
    return {
        "schema": META_SCHEMA_VERSION,
        "titleBase": str(job.get("titleBase", "")).strip(),
        "bookCount": book_count,
        "totalPages": total_pages,
        "pageLimit": effective_page_limit(job),
        "reviewed": bool(reviewed) or llm_applied,
        "llmApplied": llm_applied,
        "sourceHash": str(job.get("sourceHash", "")),
        "generatedAt": generated_at or str(job.get("createdAt", "")) or _now(),
        "generatorVersion": __version__,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)


def _load_job(job_path: Path) -> dict[str, Any]:
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"无法读取 job：{error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"job 不是合法 JSON：{error}") from error
    if not isinstance(job, dict):
        raise ValueError("job 根节点必须是对象")
    try:
        validate_job_data(job)
    except Exception as error:
        raise ValueError(f"job 校验失败：{error}") from error
    return job


def _validate_title(title: str) -> None:
    if not title:
        raise ValueError("job 缺少 titleBase")
    if len(title) > MAX_TITLE_CHARS:
        raise ValueError(
            f"书名 {title!r} 有 {len(title)} 字符，超过 {MAX_TITLE_CHARS} 字符限制"
        )
    if len(title) + 3 > MAX_BOOK_TITLE_CHARS:
        raise ValueError(
            f"书名 {title!r} 追加 -NN 后可能超过 {MAX_BOOK_TITLE_CHARS} 字符"
        )
    if any(char in title for char in ("/", "\\")) or title in (".", ".."):
        raise ValueError("书名不能包含路径分隔符")


def install_job(job_path: Path, game_dir: Path) -> InstallOutcome:
    """校验并安装 job，同时写入 P7.4 元数据；同名任务覆盖前保留 .bak。"""
    job = _load_job(job_path)
    title = str(job.get("titleBase", "")).strip()
    _validate_title(title)

    game_dir = Path(game_dir)
    if not game_dir.is_dir():
        raise ValueError(f"游戏目录不存在：{game_dir}")

    jobs_dir = game_dir / "autobook" / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    destination = jobs_dir / f"{title}.json"
    meta_path = jobs_dir / f"{title}.meta.json"

    backup: Path | None = None
    overwritten = destination.exists()
    if overwritten:
        backup = destination.with_name(destination.name + ".bak")
        shutil.copy2(destination, backup)

    _atomic_write_json(destination, job)
    reviewed = job_path.parent.name == "reviewed"
    meta = build_job_meta(job, reviewed=reviewed)
    _atomic_write_json(meta_path, meta)

    book_count, total_pages = estimate_plan(job)
    return InstallOutcome(
        destination=destination,
        meta_path=meta_path,
        backup_path=backup,
        book_count=book_count,
        total_pages=total_pages,
        overwritten=overwritten,
        reviewed=bool(meta["reviewed"]),
        llm_applied=bool(meta["llmApplied"]),
    )


def read_status(game_dir: Path) -> StatusSnapshot | None:
    """读取 AutoBook 的 status.json；缺失、损坏或 schema 不匹配时返回 None。"""
    path = Path(game_dir) / "autobook" / "status.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("schema") != STATUS_SCHEMA_VERSION:
        return None

    def text(key: str) -> str:
        value = data.get(key)
        return value if isinstance(value, str) else ""

    def number(key: str) -> int:
        value = data.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    return StatusSnapshot(
        schema=STATUS_SCHEMA_VERSION,
        run_status=text("runStatus"),
        current_job=text("currentJob"),
        next_index=number("nextIndex"),
        completed_books=number("completedBooks"),
        total_books=number("totalBooks"),
        verified_books=number("verifiedBooks"),
        reason=text("reason"),
        updated_at=text("updatedAt"),
        autobook_version=text("autoBookVersion"),
    )


def read_autobook_jars(game_dir: Path) -> list[JarInfo]:
    mods_dir = Path(game_dir) / "mods"
    if not mods_dir.is_dir():
        return []
    jars: list[JarInfo] = []
    for jar in sorted(mods_dir.glob("autobook*.jar")):
        try:
            with zipfile.ZipFile(jar) as archive:
                with archive.open("fabric.mod.json") as handle:
                    meta = json.loads(handle.read().decode("utf-8"))
        except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(meta, dict):
            continue
        version = str(meta.get("version") or "")
        depends = meta.get("depends")
        minecraft = str(depends.get("minecraft", "")) if isinstance(depends, dict) else ""
        jars.append(JarInfo(path=jar, version=version, minecraft=minecraft))
    return jars


def version_tuple(text: str) -> tuple[int, int, int]:
    match = _VERSION_RE.search(text or "")
    return tuple(int(part) for part in match.groups()) if match else (0, 0, 0)


def autobook_compat(game_dir: Path) -> tuple[str, str]:
    """返回 (状态, 说明)；状态为 ok / old / missing。"""
    jars = read_autobook_jars(game_dir)
    if not jars:
        return "missing", "未检测到 AutoBook jar（mods/ 中应有 autobook-*.jar）"
    newest = max(jars, key=lambda jar: version_tuple(jar.version))
    if version_tuple(newest.version) < version_tuple(MIN_AUTOBOOK_VERSION):
        return "old", (
            f"AutoBook {newest.version or '未知版本'} 低于 {MIN_AUTOBOOK_VERSION}，"
            "不支持任务元数据与运行状态联动"
        )
    return "ok", f"AutoBook {newest.version}（{newest.path.name}）"


def current_job_problem(status: StatusSnapshot | None, game_dir: Path) -> str:
    if status is None or not status.current_job:
        return ""
    path = Path(game_dir) / "autobook" / "jobs" / f"{status.current_job}.json"
    if not path.is_file():
        return f"当前任务文件不存在：{status.current_job}.json"
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return f"当前任务文件无法解析：{status.current_job}.json"
    if not isinstance(job, dict) or job.get("version") != 1:
        version = job.get("version") if isinstance(job, dict) else "?"
        return f"当前任务 version={version}，AutoBook 只支持 v1，可能无法运行"
    return ""


_RUN_LABELS = {
    "created": "已创建",
    "planning": "准备中",
    "queuing": "待启动",
    "running": "运行中",
    "paused": "已暂停",
    "completed": "已完成",
    "failed": "失败",
    "cancelled": "已取消",
}


def describe_status(status: StatusSnapshot) -> str:
    label = _RUN_LABELS.get(status.run_status, status.run_status or "未知")
    if not status.current_job:
        return label
    text = f"{label} · {status.current_job}"
    if status.total_books > 0:
        text += f" {status.completed_books}/{status.total_books} 本"
    if status.verified_books > 0:
        text += f"，校验 {status.verified_books}"
    if status.reason:
        text += f" · {status.reason}"
    return text
