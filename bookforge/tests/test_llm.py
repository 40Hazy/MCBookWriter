from __future__ import annotations

import json
from pathlib import Path

import pytest

from bookforge.llm import (
    SYSTEM_PROMPT_PATCH,
    SYSTEM_PROMPT_REPORT,
    LlmBlockedError,
    LlmError,
    LlmSettings,
    build_user_prompt,
    describe_profiles,
    estimate_review,
    load_settings,
    parse_issues,
    parse_patches,
    review_job,
    split_text,
)


def settings(api_key: str = "test-key", max_chars: int = 6000) -> LlmSettings:
    return LlmSettings(
        api_key=api_key,
        base_url="https://example.test/v1",
        model="test-model",
        timeout=1.0,
        max_chars=max_chars,
        key_file=Path("key.txt"),
    )


def job(text: str, index: int = 1, chapter: str = "1. test") -> dict:
    return {
        "titleBase": "T",
        "sourceHash": "abc",
        "segments": [{"index": index, "chapter": chapter, "text": text}],
    }


class FakeClient:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self.responses:
            raise LlmError("no fake response left")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_skipped_when_key_is_empty() -> None:
    report = review_job(job("正文"), settings(api_key=""), client=FakeClient([]))

    assert report["summary"]["skipped"] is True
    assert report["summary"]["issues"] == 0
    assert "API key" in report["summary"]["reason"]
    assert report["issues"] == []


def test_parse_issues_accepts_fenced_json() -> None:
    content = (
        "```json\n"
        '{"issues":[{"type":"typo","excerpt":"错字","message":"疑似 OCR 错字",'
        '"suggestion":"改为正确写法"}]}\n'
        "```"
    )

    issues = parse_issues(content)

    assert len(issues) == 1
    assert issues[0]["type"] == "typo"
    assert issues[0]["suggestion"] == "改为正确写法"


def test_parse_issues_rejects_missing_array() -> None:
    with pytest.raises(ValueError):
        parse_issues('{"result":"ok"}')


def test_review_collects_issue_metadata() -> None:
    fake = FakeClient(
        ['{"issues":[{"type":"typo","excerpt":"abc","message":"错字"}]}']
    )

    report = review_job(job("正文"), settings(), client=fake)

    assert report["summary"]["chunks"] == 1
    assert report["summary"]["issues"] == 1
    assert report["issues"][0]["segment"] == 1
    assert report["issues"][0]["chapter"] == "1. test"
    assert report["issues"][0]["chunk"] == 1


def test_review_chunks_long_text() -> None:
    text = "\n".join(["这是一段正文" * 8 for _ in range(20)])
    fake = FakeClient(['{"issues":[]}'] * 50)

    report = review_job(job(text), settings(max_chars=200), client=fake)

    assert report["summary"]["plannedChunks"] > 1
    assert report["summary"]["chunks"] == len(fake.calls)
    assert report["summary"]["issues"] == 0


def test_review_limits_chunks() -> None:
    text = "\n".join(["正文" * 20 for _ in range(20)])
    fake = FakeClient(['{"issues":[]}'] * 10)

    report = review_job(job(text), settings(max_chars=200), max_chunks=2, client=fake)

    assert report["summary"]["chunks"] == 2
    assert report["summary"]["limited"] is True


def test_sample_chunks_selects_evenly_spaced_chunks() -> None:
    text = "0123456789" * 5
    fake = FakeClient(
        ['{"issues":[{"type":"typo","excerpt":"x","message":"m"}]}'] * 3
    )

    report = review_job(
        job(text),
        settings(max_chars=10),
        sample_chunks=3,
        client=fake,
    )

    assert report["summary"]["plannedChunks"] == 5
    assert report["summary"]["sample"] == 3
    assert report["summary"]["selectedChunks"] == 3
    assert report["summary"]["chunks"] == 3
    assert {issue["chunk"] for issue in report["issues"]} == {1, 3, 5}



def test_review_records_malformed_response() -> None:
    report = review_job(job("正文"), settings(), client=FakeClient(["not json"]))

    assert report["summary"]["errors"] == 1
    assert report["summary"]["issues"] == 0
    assert report["errors"][0]["message"]


def test_report_does_not_contain_api_key() -> None:
    report = review_job(
        job("正文"),
        settings(api_key="sk-secret-value"),
        client=FakeClient(["{\"issues\":[]}"]),
    )

    assert "sk-secret-value" not in json.dumps(report, ensure_ascii=False)


def test_split_text_preserves_content() -> None:
    text = "\n".join(["a" * 50 for _ in range(10)])

    chunks = split_text(text, 80)

    assert "".join(chunks) == text
    assert all(len(chunk) <= 80 for chunk in chunks)


def test_load_settings_reads_key_and_config(tmp_path: Path) -> None:
    key_file = tmp_path / "llm_api_key.txt"
    key_file.write_text("  sk-test-key  \n", encoding="utf-8")
    config_file = tmp_path / "llm_config.json"
    config_file.write_text(
        json.dumps(
            {
                "base_url": "https://llm.example/v1/",
                "model": "demo-model",
                "timeout": 42,
                "max_chars": 4000,
            }
        ),
        encoding="utf-8",
    )

    loaded = load_settings(key_file=key_file, config_file=config_file)

    assert loaded.enabled
    assert loaded.api_key == "sk-test-key"
    assert loaded.base_url == "https://llm.example/v1"
    assert loaded.model == "demo-model"
    assert loaded.timeout == 42
    assert loaded.max_chars == 4000


def test_load_settings_with_empty_key_is_disabled(tmp_path: Path) -> None:
    key_file = tmp_path / "empty_key.txt"
    key_file.write_text("", encoding="utf-8")

    loaded = load_settings(
        key_file=key_file,
        base_url="https://example.test/v1",
        model="test-model",
        config_file=tmp_path / "missing.json",
    )

    assert not loaded.enabled


def test_patch_mode_returns_find_replace_and_chunk_location() -> None:
    text = "这里有错误"
    fake = FakeClient(
        [
            '{"issues":[{"type":"typo","find":"错误","replace":"正确",'
            '"reason":"形近字","confidence":"high"}]}'
        ]
    )

    report = review_job(
        job(text),
        settings(max_chars=200),
        mode="patch",
        client=fake,
    )

    assert report["mode"] == "patch"
    issue = report["issues"][0]
    assert issue["find"] == "错误"
    assert issue["replace"] == "正确"
    assert issue["chunkStart"] == 0
    assert issue["chunkEnd"] == len(text)
    assert issue["chunkHash"]
    assert issue["confidence"] == "high"


def test_blocked_chunk_is_recorded_and_review_continues() -> None:
    fake = FakeClient(
        [
            LlmBlockedError("content_filter"),
            '{"issues":[]}',
        ]
    )

    report = review_job(
        job("a" * 300),
        settings(max_chars=200),
        client=fake,
    )

    assert report["summary"]["chunks"] == 2
    assert report["summary"]["blocked"] == 1
    assert report["summary"]["errors"] == 0
    assert report["blocked"][0]["chunk"] == 1


def test_api_error_stops_review() -> None:
    fake = FakeClient([LlmError("HTTP 500")])

    report = review_job(
        job("a" * 300),
        settings(max_chars=200),
        client=fake,
    )

    assert report["summary"]["chunks"] == 1
    assert report["summary"]["errors"] == 1
    assert report["summary"]["blocked"] == 0


def test_parse_patches_skips_empty_find_and_defaults_confidence() -> None:
    patches = parse_patches(
        '{"issues":['
        '{"type":"typo","find":"","replace":"x"},'
        '{"type":"typo","find":"错","replace":"对"}'
        "]}"
    )

    assert len(patches) == 1
    assert patches[0]["confidence"] == "low"


def test_patch_prompt_contains_target_and_glossary() -> None:
    prompt = build_user_prompt(
        "1. test",
        "正文",
        mode="patch",
        glossary=["叶文洁", "智子"],
    )

    assert "<target>" in prompt
    assert "</target>" in prompt
    assert "叶文洁、智子" in prompt


def test_load_settings_applies_profile_and_merges_max_delta(tmp_path: Path) -> None:
    key_file = tmp_path / "key.txt"
    key_file.write_text("sk-test", encoding="utf-8")
    glossary = tmp_path / "glossary.txt"
    glossary.write_text("叶文洁\n", encoding="utf-8")
    config_file = tmp_path / "llm_config.json"
    config_file.write_text(
        json.dumps(
            {
                "base_url": "https://global.example/v1",
                "model": "global-model",
                "max_chars": 6000,
                "max_tokens": 4096,
                "thinking": False,
                "max_delta": {"typo": 2, "missing": 10},
                "profiles": {
                    "三体1": {
                        "model": "book-model",
                        "style": "保留科幻术语",
                        "glossary": str(glossary),
                        "min_confidence": "medium",
                        "max_chars": 2500,
                        "max_tokens": 12000,
                        "thinking": True,
                        "max_delta": {"typo": 3},
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = load_settings(
        key_file=key_file,
        profile="三体1",
        config_file=config_file,
    )

    assert loaded.profile_name == "三体1"
    assert loaded.model == "book-model"
    assert loaded.base_url == "https://global.example/v1"
    assert loaded.style == "保留科幻术语"
    assert loaded.glossary_file == glossary
    assert loaded.min_confidence == "medium"
    assert loaded.max_delta == {"typo": 3, "missing": 10}
    assert loaded.max_chars == 2500
    assert loaded.max_tokens == 12000
    assert loaded.thinking is True


def test_missing_profile_falls_back_or_fails_when_strict(tmp_path: Path) -> None:
    config_file = tmp_path / "llm_config.json"
    config_file.write_text(
        json.dumps({"base_url": "https://global.example/v1", "model": "global-model"}),
        encoding="utf-8",
    )

    loaded = load_settings(profile="未配置的书", config_file=config_file)
    assert loaded.profile_name == ""
    assert loaded.model == "global-model"

    with pytest.raises(ValueError):
        load_settings(
            profile="未配置的书",
            strict_profile=True,
            config_file=config_file,
        )


def test_report_includes_profile_policy_and_style() -> None:
    settings_with_style = LlmSettings(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        timeout=1.0,
        max_chars=6000,
        key_file=Path("key.txt"),
        style="保留作者用词",
        min_confidence="medium",
        max_delta={"typo": 4},
        profile_name="三体1",
    )
    fake = FakeClient(['{"issues":[]}'])

    report = review_job(job("正文"), settings_with_style, client=fake)

    assert report["settings"]["profile"] == "三体1"
    assert report["settings"]["style"] == "保留作者用词"
    assert report["policy"] == {"minConfidence": "medium", "maxDelta": {"typo": 4}}
    assert "【本书特定要求】保留作者用词" in fake.calls[0][0]


def test_report_aggregates_token_usage() -> None:
    fake = FakeClient(['{"issues":[]}'])
    fake.last_usage = {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
        "completion_tokens_details": {"reasoning_tokens": 0},
    }

    report = review_job(job("正文"), settings(), client=fake)

    assert report["usage"] == {
        "promptTokens": 100,
        "completionTokens": 20,
        "reasoningTokens": 0,
        "totalTokens": 120,
    }


def test_review_progress_and_cancel() -> None:
    import threading

    event = threading.Event()
    progress: list[tuple[int, int, str]] = []

    def callback(done: int, total: int, message: str) -> None:
        progress.append((done, total, message))
        if done >= 1:
            event.set()

    fake = FakeClient(['{"issues":[]}'] * 3)
    report = review_job(
        job("a" * 300),
        settings(max_chars=200),
        client=fake,
        progress=callback,
        cancel=event,
    )

    assert len(fake.calls) == 1
    assert report["summary"]["cancelled"] is True
    assert report["summary"]["chunks"] == 1
    assert progress == [(1, 2, "1. test #1")]


def test_prompts_preserve_classical_chinese_variants() -> None:
    for prompt in (SYSTEM_PROMPT_REPORT, SYSTEM_PROMPT_PATCH):
        assert "通假字" in prompt
        assert "古今异义" in prompt
        assert "异体字" in prompt

    assert "不得以现代汉语规范" in SYSTEM_PROMPT_PATCH


def test_estimate_review_uses_sampling_without_calling_client() -> None:
    result = estimate_review(
        job("0123456789" * 5),
        settings(max_chars=10),
        sample_chunks=3,
        mode="report",
    )

    assert result["plannedChunks"] == 5
    assert result["selectedChunks"] == 3
    assert result["sample"] == 3
    assert result["plannedChars"] == 50
    assert result["selectedChars"] == 30
    assert result["estimated"]["promptTokens"] > 0
    assert result["estimated"]["completionTokens"] == 3 * 360
    assert result["cost"] is None


def test_estimate_review_computes_cost_with_pricing() -> None:
    priced = LlmSettings(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        timeout=1.0,
        max_chars=10,
        key_file=Path("key.txt"),
        pricing={
            "currency": "CNY",
            "inputPerMillion": 2.0,
            "outputPerMillion": 3.0,
            "offpeakFactor": 0.5,
        },
    )

    result = estimate_review(job("正文"), priced, mode="patch")

    assert result["estimated"]["completionTokens"] == 300
    assert result["cost"]["currency"] == "CNY"
    assert result["cost"]["low"] <= result["cost"]["high"]


def test_load_settings_reads_pricing(tmp_path: Path) -> None:
    config_file = tmp_path / "llm_config.json"
    config_file.write_text(
        json.dumps(
            {
                "model": "demo-model",
                "pricing": {
                    "currency": "CNY",
                    "inputPerMillion": 2.0,
                    "outputPerMillion": 3.0,
                    "offpeakFactor": 0.5,
                },
            }
        ),
        encoding="utf-8",
    )

    loaded = load_settings(config_file=config_file)

    assert loaded.pricing["inputPerMillion"] == 2.0
    assert loaded.pricing["outputPerMillion"] == 3.0
    assert loaded.pricing["offpeakFactor"] == 0.5
    assert loaded.pricing["currency"] == "CNY"


def test_describe_profiles_lists_global_and_book_profiles(tmp_path: Path) -> None:
    key_file = tmp_path / "key.txt"
    key_file.write_text("sk-secret", encoding="utf-8")
    glossary = tmp_path / "glossary.txt"
    glossary.write_text("# 注释\n叶文洁\n智子\n", encoding="utf-8")
    config_file = tmp_path / "llm_config.json"
    config_file.write_text(
        json.dumps(
            {
                "base_url": "https://global.example/v1",
                "model": "global-model",
                "max_chars": 4000,
                "key_file": str(key_file),
                "glossary": str(glossary),
                "profiles": {
                    "三体1": {
                        "model": "book-model",
                        "style": "保留科幻术语",
                        "max_chars": 2500,
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    profiles = describe_profiles(config_file)

    assert [item["name"] for item in profiles] == ["-", "三体1"]
    assert profiles[0]["model"] == "global-model"
    assert profiles[1]["model"] == "book-model"
    assert profiles[1]["maxChars"] == 2500
    assert profiles[1]["keyConfigured"] is True
    assert profiles[1]["glossaryTerms"] == 2
    assert profiles[1]["style"] == "保留科幻术语"
    assert "sk-secret" not in json.dumps(profiles, ensure_ascii=False)



