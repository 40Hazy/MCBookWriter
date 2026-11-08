from __future__ import annotations

import hashlib

import pytest

from bookforge.patch import apply_patches, build_unified_diff


def make_job(text: str) -> dict:
    return {
        "version": 1,
        "titleBase": "T",
        "pageLimit": 100,
        "sourceHash": "a" * 64,
        "options": {"stripFormatting": False, "llmApplied": False},
        "segments": [{"index": 1, "chapter": "1. test", "text": text}],
    }


def make_issue(
    text: str,
    find: str,
    replace: str,
    *,
    issue_type: str = "typo",
    confidence: str = "high",
    chunk_start: int = 0,
    chunk_end: int | None = None,
    chunk_hash: str | None = None,
) -> dict:
    end = len(text) if chunk_end is None else chunk_end
    chunk = text[chunk_start:end]
    digest = (
        chunk_hash
        if chunk_hash is not None
        else hashlib.sha256(chunk.encode("utf-8")).hexdigest()
    )
    return {
        "type": issue_type,
        "find": find,
        "replace": replace,
        "reason": "test",
        "confidence": confidence,
        "segment": 1,
        "chunk": 1,
        "chunkStart": chunk_start,
        "chunkEnd": end,
        "chunkHash": digest,
    }


def test_applies_minimal_patch() -> None:
    job = make_job("这是一个错别字。")

    result = apply_patches(job, [make_issue("这是一个错别字。", "错别字", "错字")])

    assert result.applied_count == 1
    assert result.rejected_count == 0
    assert result.segments_changed == 1
    assert result.job["segments"][0]["text"] == "这是一个错字。"
    assert result.job["options"]["llmApplied"] is True


def test_rejects_ambiguous_find() -> None:
    job = make_job("错误错误")

    result = apply_patches(job, [make_issue("错误错误", "错误", "正确")])

    assert result.applied_count == 0
    assert result.rejected_count == 1


def test_rejects_newline_change() -> None:
    text = "第一行\n第二行"
    job = make_job(text)

    result = apply_patches(job, [make_issue(text, text, "第一行第二行")])

    assert result.applied_count == 0
    assert "换行" in result.rejected[0]["reason"]


def test_rejects_low_confidence_by_default() -> None:
    job = make_job("错误")

    result = apply_patches(
        job,
        [make_issue("错误", "错", "对", confidence="low")],
    )

    assert result.applied_count == 0
    assert "confidence" in result.rejected[0]["reason"]


def test_applies_medium_when_threshold_allows() -> None:
    job = make_job("错误")

    result = apply_patches(
        job,
        [make_issue("错误", "错", "对", confidence="medium")],
        min_confidence="medium",
    )

    assert result.applied_count == 1
    assert result.job["segments"][0]["text"] == "对误"


def test_applies_multiple_patches_descending() -> None:
    text = "甲乙丙"
    job = make_job(text)
    issues = [
        make_issue(text, "甲", "A"),
        make_issue(text, "丙", "C"),
    ]

    result = apply_patches(job, issues)

    assert result.applied_count == 2
    assert result.job["segments"][0]["text"] == "A乙C"


def test_rejects_hash_mismatch() -> None:
    text = "错误"
    job = make_job(text)

    result = apply_patches(
        job,
        [make_issue(text, "错", "对", chunk_hash="bad-hash")],
    )

    assert result.applied_count == 0
    assert "chunkHash" in result.rejected[0]["reason"]


def test_rejects_ad_type() -> None:
    text = "广告"
    job = make_job(text)

    result = apply_patches(
        job,
        [make_issue(text, "广告", "", issue_type="ad")],
    )

    assert result.applied_count == 0
    assert "ad" in result.rejected[0]["reason"]


def test_rejects_overlapping_patches() -> None:
    text = "甲乙丙"
    job = make_job(text)
    issues = [
        make_issue(text, "甲乙", "A"),
        make_issue(text, "乙丙", "B"),
    ]

    result = apply_patches(job, issues)

    assert result.applied_count == 1
    assert result.rejected_count == 1
    assert "重叠" in result.rejected[0]["reason"]


def test_sets_llm_applied_false_when_nothing_applied() -> None:
    job = make_job("错误")

    result = apply_patches(job, [])

    assert result.applied_count == 0
    assert result.job["options"]["llmApplied"] is False


def test_max_delta_override_allows_larger_change() -> None:
    job = make_job("甲")
    issue = make_issue("甲", "甲", "ABCD")

    default_result = apply_patches(job, [issue])
    assert default_result.applied_count == 0

    override_result = apply_patches(job, [issue], max_delta={"typo": 5})
    assert override_result.applied_count == 1
    assert override_result.job["segments"][0]["text"] == "ABCD"


def test_rejects_unknown_max_delta_type() -> None:
    job = make_job("错误")

    with pytest.raises(ValueError):
        apply_patches(
            job,
            [make_issue("错误", "错", "对")],
            max_delta={"unknown": 5},
        )


def test_build_unified_diff_contains_changes() -> None:
    job = make_job("错误")
    result = apply_patches(job, [make_issue("错误", "错", "对")])

    diff = build_unified_diff(job, result.job)

    assert "segment-1-before" in diff
    assert "-错误" in diff
    assert "+对误" in diff


def test_build_unified_diff_is_empty_without_changes() -> None:
    job = make_job("错误")
    result = apply_patches(job, [])

    assert build_unified_diff(job, result.job) == ""

