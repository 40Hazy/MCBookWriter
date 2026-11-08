from __future__ import annotations

import copy
import difflib
import hashlib
from dataclasses import dataclass
from typing import Any

CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
MAX_DELTA = {
    "typo": 2,
    "punctuation": 10,
    "missing": 30,
    "extra": 30,
    "garbled": 40,
    "broken": 10,
    "other": 10,
}
PATCHABLE_TYPES = {
    "typo",
    "missing",
    "extra",
    "garbled",
    "duplicate",
    "broken",
    "punctuation",
    "other",
}


@dataclass(frozen=True)
class PatchApplyResult:
    job: dict[str, Any]
    applied: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    segments_changed: int

    @property
    def applied_count(self) -> int:
        return len(self.applied)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)


def _reject(
    rejected: list[dict[str, Any]],
    issue: dict[str, Any],
    reason: str,
) -> None:
    rejected.append(
        {
            "segment": issue.get("segment"),
            "chunk": issue.get("chunk"),
            "type": issue.get("type", ""),
            "find": str(issue.get("find", ""))[:80],
            "reason": reason,
        }
    )


def _allowed_delta(
    issue_type: str,
    find: str,
    overrides: dict[str, int] | None,
) -> int:
    if overrides and issue_type in overrides:
        return int(overrides[issue_type])
    if issue_type == "duplicate":
        return max(20, min(200, len(find) // 2))
    return MAX_DELTA.get(issue_type, 10)


def build_unified_diff(
    original_job: dict[str, Any],
    reviewed_job: dict[str, Any],
) -> str:
    original_segments = (
        original_job.get("segments")
        if isinstance(original_job.get("segments"), list)
        else []
    )
    reviewed_segments = (
        reviewed_job.get("segments")
        if isinstance(reviewed_job.get("segments"), list)
        else []
    )

    diffs: list[str] = []
    for original, reviewed in zip(original_segments, reviewed_segments):
        if not isinstance(original, dict) or not isinstance(reviewed, dict):
            continue
        before = str(original.get("text", ""))
        after = str(reviewed.get("text", ""))
        if before == after:
            continue
        index = original.get("index", "?")
        diff = list(
            difflib.unified_diff(
                before.splitlines(),
                after.splitlines(),
                fromfile=f"segment-{index}-before",
                tofile=f"segment-{index}-after",
                lineterm="",
            )
        )
        if diff:
            diffs.append("\n".join(diff))
    return "\n\n".join(diffs)


def apply_patches(
    job: dict[str, Any],
    issues: list[dict[str, Any]],
    *,
    min_confidence: str = "high",
    max_delta: dict[str, int] | None = None,
) -> PatchApplyResult:
    if min_confidence not in CONFIDENCE_RANK:
        raise ValueError("min_confidence 必须是 high、medium 或 low")
    if max_delta:
        for key, value in max_delta.items():
            if key not in PATCHABLE_TYPES:
                raise ValueError(f"未知 max_delta 类型: {key}")
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"max_delta.{key} 必须是非负整数")

    reviewed = copy.deepcopy(job)
    segments = reviewed.get("segments") if isinstance(reviewed.get("segments"), list) else []
    segment_map = {
        segment.get("index"): segment
        for segment in segments
        if isinstance(segment, dict)
    }

    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    intervals: dict[Any, list[tuple[int, int]]] = {}

    for issue in issues:
        if not isinstance(issue, dict):
            continue
        issue_type = str(issue.get("type", "other")).strip().lower()
        find = str(issue.get("find", ""))
        replace = str(issue.get("replace", ""))
        confidence = str(issue.get("confidence", "low")).strip().lower()
        segment_index = issue.get("segment")
        segment = segment_map.get(segment_index)

        if issue_type == "ad":
            _reject(rejected, issue, "ad 类型不自动应用，请人工处理")
            continue
        if issue_type not in PATCHABLE_TYPES:
            _reject(rejected, issue, f"不支持的类型: {issue_type}")
            continue
        if not find.strip() or find == replace:
            _reject(rejected, issue, "find 为空或与 replace 相同")
            continue
        if len(find) > 200:
            _reject(rejected, issue, "find 过长")
            continue
        if CONFIDENCE_RANK.get(confidence, 0) < CONFIDENCE_RANK[min_confidence]:
            _reject(rejected, issue, f"confidence={confidence} 低于阈值 {min_confidence}")
            continue
        if not isinstance(segment, dict):
            _reject(rejected, issue, "segment 不存在")
            continue

        text = str(segment.get("text", ""))
        chunk_start = issue.get("chunkStart")
        chunk_end = issue.get("chunkEnd")
        if not isinstance(chunk_start, int) or not isinstance(chunk_end, int):
            _reject(rejected, issue, "缺少 chunk 位置")
            continue
        if chunk_start < 0 or chunk_end > len(text) or chunk_start >= chunk_end:
            _reject(rejected, issue, "chunk 位置越界")
            continue

        chunk = text[chunk_start:chunk_end]
        expected_hash = str(issue.get("chunkHash", ""))
        actual_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
        if not expected_hash or expected_hash != actual_hash:
            _reject(rejected, issue, "chunkHash 不一致，job 可能已变更")
            continue
        if chunk.count(find) != 1:
            _reject(rejected, issue, "find 在目标块中不唯一或不存在")
            continue

        delta = abs(len(replace) - len(find))
        if delta > _allowed_delta(issue_type, find, max_delta):
            _reject(rejected, issue, f"修改长度 {delta} 超出该类型允许范围")
            continue
        if issue_type != "punctuation" and find.count("\n") != replace.count("\n"):
            _reject(rejected, issue, "修改了换行结构，需人工复核")
            continue

        local_start = chunk.find(find)
        absolute_start = chunk_start + local_start
        absolute_end = absolute_start + len(find)
        overlap = any(
            absolute_start < used_end and absolute_end > used_start
            for used_start, used_end in intervals.get(segment_index, [])
        )
        if overlap:
            _reject(rejected, issue, "与其他补丁重叠")
            continue

        intervals.setdefault(segment_index, []).append((absolute_start, absolute_end))
        applied.append(
            {
                "segment": segment_index,
                "chapter": issue.get("chapter", segment.get("chapter", "")),
                "chunk": issue.get("chunk"),
                "type": issue_type,
                "find": find,
                "replace": replace,
                "confidence": confidence,
                "reason": str(issue.get("reason", ""))[:200],
                "start": absolute_start,
            }
        )

    by_segment: dict[Any, list[dict[str, Any]]] = {}
    for patch in applied:
        by_segment.setdefault(patch["segment"], []).append(patch)

    for segment_index, patches in by_segment.items():
        segment = segment_map[segment_index]
        text = str(segment.get("text", ""))
        for patch in sorted(patches, key=lambda item: item["start"], reverse=True):
            start = patch["start"]
            end = start + len(patch["find"])
            text = text[:start] + patch["replace"] + text[end:]
        segment["text"] = text

    options = reviewed.get("options")
    if not isinstance(options, dict):
        options = {}
    options["llmApplied"] = bool(options.get("llmApplied")) or bool(applied)
    reviewed["options"] = options

    return PatchApplyResult(
        job=reviewed,
        applied=applied,
        rejected=rejected,
        segments_changed=len(by_segment),
    )
