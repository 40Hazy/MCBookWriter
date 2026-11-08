from __future__ import annotations

import hashlib
import http.client
import json
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

DEFAULT_BASE_URL = "https://api.deepseek.com/"
DEFAULT_MODEL = "deepseek-flash"
DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_CHARS = 6000
MAX_ISSUES_PER_CHUNK = 50
MAX_REPORT_ISSUES = 5000

BOOKFORGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEY_FILE = BOOKFORGE_ROOT / "keys" / "llm_api_key.txt"
DEFAULT_CONFIG_FILE = BOOKFORGE_ROOT / "keys" / "llm_config.json"
DEFAULT_GLOSSARY_FILE = BOOKFORGE_ROOT / "keys" / "glossary.txt"

ALLOWED_ISSUE_TYPES = {
    "typo",
    "missing",
    "extra",
    "garbled",
    "duplicate",
    "broken",
    "punctuation",
    "ad",
    "other",
}

SYSTEM_PROMPT_REPORT = (
    "你是一名保守的中文图书校对员。只报告可确定的转录错误，不改写原文。"
    "只报告：OCR 错字、缺字、多字、乱码、重复粘贴、明显缺失标点、残留广告或网址。"
    "不要报告：风格、断句偏好、异体字/古字、通假字、古今字、古今异义、"
    "古汉语语法与词义、文学修辞（叠词、反复、对仗）、标点风格、语序或改写建议。"
    "不得仅因不符合现代常见写法就判定为错误：古籍、校注本中的通假、借字、"
    "异读、古今异义均属正常文本，不得当作错字。"
    "无法确定时不要报告。"
    "只输出严格 JSON，不要 Markdown，不要解释："
    '{"issues":[{"type":"typo|missing|extra|garbled|duplicate|broken|ad|other",'
    '"excerpt":"原文片段（不超过40字）","message":"问题说明",'
    '"suggestion":"建议（可为空）","confidence":"high|medium|low"}]}。'
    '如果没有问题，输出 {"issues":[]}。'
)

SYSTEM_PROMPT_PATCH = (
    "你是一名保守的中文小说校对员。你的唯一任务是修复明确的转录错误，不是改写作品。"
    "【必须保留】作者的用词、语序、语气、标点风格、段落与换行；"
    "异体字、古字、通假字、古今字、古今异义、古汉语语法与词义；"
    "人名、地名、术语、专有名词、外语原文、数字、章节标题；"
    "看似重复但可能是作者有意为之的句子。"
    "【只允许修复】1) OCR 形近字错误，且上下文能唯一确定；"
    "2) 明显的缺字、多字、乱码、重复粘贴；"
    "3) 明确的标点或断行错误，但不得统一作者原有的标点习惯。"
    "【禁止】润色、改写、缩写、扩写、调整语序、替换同义词；"
    "不得以现代汉语规范为由改写古汉语用字、通假字或古今异义词；"
    "以“敏感”“不雅”“不通顺”为由删除或改写内容；猜测补写缺失情节；修改术语表内的词。"
    "【不确定时】不要修改，输出低置信度 issue 或直接不报。"
    "只输出严格 JSON，不要 Markdown，不要解释："
    '{"issues":[{"type":"typo|missing|extra|garbled|duplicate|punctuation|ad|other",'
    '"find":"原文逐字片段，不超过30字，在目标块中唯一",'
    '"replace":"最小修改后的文本",'
    '"reason":"不超过40字","confidence":"high|medium|low"}]}。'
    '如果没有问题，输出 {"issues":[]}。'
)

SYSTEM_PROMPT = SYSTEM_PROMPT_REPORT


class LlmError(RuntimeError):
    pass


class LlmBlockedError(LlmError):
    pass


class ChatClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        ...


@dataclass(frozen=True)
class LlmSettings:
    api_key: str
    base_url: str
    model: str
    timeout: float
    max_chars: int
    key_file: Path
    temperature: float = 0.0
    max_tokens: int | None = None
    thinking: bool | None = None
    style: str = ""
    min_confidence: str = "high"
    max_delta: dict[str, int] = field(default_factory=dict)
    glossary_file: Path | None = None
    profile_name: str = ""
    pricing: dict[str, Any] = field(default_factory=dict)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BOOKFORGE_ROOT / path


def _parse_optional_bool(value: Any, name: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "on", "yes"}:
        return True
    if text in {"false", "0", "off", "no"}:
        return False
    raise ValueError(f"{name} 必须是布尔值")


def load_settings(
    *,
    key_file: Path | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
    max_chars: int | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    thinking: bool | None = None,
    glossary: Path | None = None,
    profile: str | None = None,
    strict_profile: bool = False,
    config_file: Path | None = None,
) -> LlmSettings:
    config = _read_json(config_file or DEFAULT_CONFIG_FILE)
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
    profile_name = (profile or "").strip()
    profile_data = profiles.get(profile_name) if profile_name else {}
    if profile_name and not isinstance(profile_data, dict):
        if strict_profile:
            raise ValueError(f"未知 LLM profile: {profile_name}")
        profile_name = ""
        profile_data = {}
    if not isinstance(profile_data, dict):
        profile_data = {}

    def choose(name: str, cli_value=None, env_name: str | None = None, default=None):
        if cli_value is not None:
            return cli_value
        if env_name and os.environ.get(env_name):
            return os.environ[env_name]
        if name in profile_data:
            return profile_data[name]
        if name in config:
            return config[name]
        return default

    key_value = choose("key_file", key_file, "BOOKFORGE_LLM_KEY_FILE", None)
    path = _resolve_path(key_value) if key_value else DEFAULT_KEY_FILE
    api_key = ""
    if path.is_file():
        api_key = path.read_text(encoding="utf-8").strip().strip('"').strip("'")

    resolved_base = str(
        choose("base_url", base_url, "BOOKFORGE_LLM_BASE_URL", DEFAULT_BASE_URL)
    ).rstrip("/")
    resolved_model = str(
        choose("model", model, "BOOKFORGE_LLM_MODEL", DEFAULT_MODEL)
    )
    resolved_timeout = float(choose("timeout", timeout, None, DEFAULT_TIMEOUT))
    resolved_max_chars = int(choose("max_chars", max_chars, None, DEFAULT_MAX_CHARS))
    resolved_temperature = float(choose("temperature", temperature, None, 0.0))
    raw_max_tokens = choose("max_tokens", max_tokens, None, None)
    resolved_max_tokens = int(raw_max_tokens) if raw_max_tokens is not None else None
    resolved_thinking = _parse_optional_bool(
        choose("thinking", thinking, None, None),
        "thinking",
    )

    if resolved_timeout <= 0:
        raise ValueError("LLM timeout 必须大于 0")
    if resolved_max_chars < 200:
        raise ValueError("LLM max_chars 不能小于 200")
    if not 0 <= resolved_temperature <= 2:
        raise ValueError("LLM temperature 必须在 0–2 之间")
    if resolved_max_tokens is not None and resolved_max_tokens <= 0:
        raise ValueError("LLM max_tokens 必须大于 0")

    glossary_value = (
        glossary
        if glossary is not None
        else (profile_data.get("glossary") or config.get("glossary"))
    )
    if glossary_value:
        glossary_file = _resolve_path(glossary_value)
    else:
        glossary_file = DEFAULT_GLOSSARY_FILE if DEFAULT_GLOSSARY_FILE.is_file() else None

    raw_delta: dict[str, Any] = {}
    if isinstance(config.get("max_delta"), dict):
        raw_delta.update(config["max_delta"])
    if isinstance(profile_data.get("max_delta"), dict):
        raw_delta.update(profile_data["max_delta"])
    max_delta: dict[str, int] = {}
    for key, value in raw_delta.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and value >= 0:
            max_delta[str(key)] = int(value)

    min_confidence = str(choose("min_confidence", None, None, "high")).strip().lower()
    if min_confidence not in {"high", "medium", "low"}:
        raise ValueError("min_confidence 必须是 high、medium 或 low")

    style = str(choose("style", None, None, "") or "").strip()

    raw_pricing = config.get("pricing")
    pricing: dict[str, Any] = {}
    if isinstance(raw_pricing, dict):
        for price_key in ("inputPerMillion", "outputPerMillion", "offpeakFactor"):
            value = raw_pricing.get(price_key)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and value >= 0
            ):
                pricing[price_key] = float(value)
        currency = str(raw_pricing.get("currency", "")).strip()
        if currency:
            pricing["currency"] = currency

    return LlmSettings(
        api_key=api_key,
        base_url=resolved_base,
        model=resolved_model,
        timeout=resolved_timeout,
        max_chars=resolved_max_chars,
        key_file=path,
        temperature=resolved_temperature,
        max_tokens=resolved_max_tokens,
        thinking=resolved_thinking,
        style=style,
        min_confidence=min_confidence,
        max_delta=max_delta,
        glossary_file=glossary_file,
        profile_name=profile_name if profile_data else "",
        pricing=pricing,
    )


class OpenAiCompatibleClient:
    def __init__(self, settings: LlmSettings) -> None:
        self.settings = settings
        self.last_usage: dict[str, Any] | None = None

    def complete(self, system: str, user: str) -> str:
        if not self.settings.enabled:
            raise LlmError("未配置 LLM API key")

        url = f"{self.settings.base_url}/chat/completions"
        payload = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.settings.max_tokens is not None:
            payload["max_tokens"] = self.settings.max_tokens
        if self.settings.thinking is not None:
            payload["thinking"] = {
                "type": "enabled" if self.settings.thinking else "disabled"
            }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.api_key}",
                "User-Agent": "bookforge/0.6.0",
            },
            method="POST",
        )

        body = self._post(request)

        try:
            data = json.loads(body)
        except json.JSONDecodeError as error:
            raise LlmError("LLM 返回内容不是 JSON") from error
        self.last_usage = (
            data.get("usage")
            if isinstance(data, dict) and isinstance(data.get("usage"), dict)
            else None
        )

        if isinstance(data, dict) and isinstance(data.get("error"), dict):
            message = str(data["error"].get("message", ""))
            if _looks_blocked(message):
                raise LlmBlockedError("LLM 内容审核拦截")
            raise LlmError(f"LLM 返回错误: {message[:300]}")

        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices:
            raise LlmError("LLM 返回缺少 choices")
        choice = choices[0] if isinstance(choices[0], dict) else {}
        finish_reason = str(choice.get("finish_reason", ""))
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = message.get("content")
        if finish_reason == "content_filter":
            raise LlmBlockedError("LLM 内容审核拦截 (finish_reason=content_filter)")
        if finish_reason == "length":
            usage = data.get("usage") if isinstance(data, dict) else None
            preview = content[:200] if isinstance(content, str) else ""
            raise LlmError(
                "LLM 输出被截断 (finish_reason=length)，请减小 max_chars 或增大 max_tokens"
                f" (usage={usage}, preview={preview!r})"
            )

        if not isinstance(content, str):
            raise LlmError("LLM 返回缺少 message.content")
        return content

    def _post(self, request: urllib.request.Request) -> str:
        last_error: LlmError | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.settings.timeout,
                ) as response:
                    return response.read().decode("utf-8")
            except urllib.error.HTTPError as error:
                snippet = error.read().decode("utf-8", "replace")[:300]
                if error.code == 429 or 500 <= error.code < 600:
                    last_error = LlmError(f"LLM HTTP {error.code}: {snippet}")
                elif _looks_blocked(snippet):
                    raise LlmBlockedError(
                        f"LLM 内容审核拦截 (HTTP {error.code})"
                    ) from error
                else:
                    raise LlmError(f"LLM HTTP {error.code}: {snippet}") from error
            except (
                urllib.error.URLError,
                http.client.HTTPException,
                ConnectionError,
                TimeoutError,
            ) as error:
                reason = getattr(error, "reason", error)
                last_error = LlmError(f"LLM 连接异常: {reason}")

            if attempt < 2:
                time.sleep(1 + attempt * 2)

        raise last_error or LlmError("LLM 请求失败")


def _looks_blocked(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("content_filter", "content_policy", "content policy", "moderation")
    )


def split_text_with_offsets(text: str, max_chars: int) -> list[tuple[int, int, str]]:
    if max_chars < 1:
        raise ValueError("max_chars 必须大于 0")
    if not text:
        return []

    chunks: list[tuple[int, int, str]] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            newline = text.rfind("\n", start, end)
            if newline > start + max_chars // 2:
                end = newline + 1
        chunk = text[start:end]
        if chunk.strip():
            chunks.append((start, end, chunk))
        start = end
    return chunks


def split_text(text: str, max_chars: int) -> list[str]:
    return [chunk for _, _, chunk in split_text_with_offsets(text, max_chars)]


@dataclass(frozen=True)
class ReviewPlan:
    planned_chunks: int
    selected_chunks: int
    sample: int
    planned_chars: int
    selected_chars: int
    chunks: list[dict[str, Any]]


def plan_review(
    job: dict[str, Any],
    max_chars: int,
    *,
    max_chunks: int = 0,
    sample_chunks: int = 0,
) -> ReviewPlan:
    if max_chars < 1:
        raise ValueError("max_chars 必须大于 0")
    if sample_chunks < 0:
        raise ValueError("sample_chunks 不能小于 0")

    segments = job.get("segments") if isinstance(job.get("segments"), list) else []
    pending: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        segment_index = segment.get("index")
        chapter = str(segment.get("chapter", ""))
        for chunk_index, (chunk_start, chunk_end, chunk) in enumerate(
            split_text_with_offsets(str(segment.get("text", "")), max_chars),
            start=1,
        ):
            pending.append(
                {
                    "segment": segment_index,
                    "chapter": chapter,
                    "chunk": chunk_index,
                    "chunkStart": chunk_start,
                    "chunkEnd": chunk_end,
                    "text": chunk,
                }
            )

    total_chunks = len(pending)
    selected = pending
    if sample_chunks and sample_chunks < total_chunks:
        if sample_chunks == 1:
            indices = [total_chunks // 2]
        else:
            indices = sorted(
                {
                    i * (total_chunks - 1) // (sample_chunks - 1)
                    for i in range(sample_chunks)
                }
            )
        selected = [pending[index] for index in indices]
    if max_chunks:
        selected = selected[:max_chunks]

    return ReviewPlan(
        planned_chunks=total_chunks,
        selected_chunks=len(selected),
        sample=min(sample_chunks, total_chunks) if sample_chunks else 0,
        planned_chars=sum(len(item["text"]) for item in pending),
        selected_chars=sum(len(item["text"]) for item in selected),
        chunks=selected,
    )


ESTIMATE_TOKENS_PER_CHAR = 0.6
ESTIMATE_PROMPT_OVERHEAD_TOKENS = 240
ESTIMATE_OUTPUT_TOKENS = {"report": 360, "patch": 300}


def _estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    pricing: dict[str, Any],
) -> dict[str, Any] | None:
    input_rate = pricing.get("inputPerMillion")
    output_rate = pricing.get("outputPerMillion")
    if not isinstance(input_rate, (int, float)) or not isinstance(output_rate, (int, float)):
        return None
    peak = (
        prompt_tokens / 1_000_000 * float(input_rate)
        + completion_tokens / 1_000_000 * float(output_rate)
    )
    factor = pricing.get("offpeakFactor")
    low = (
        peak * float(factor)
        if isinstance(factor, (int, float)) and not isinstance(factor, bool)
        else None
    )
    return {
        "currency": str(pricing.get("currency") or "CNY"),
        "low": low,
        "high": peak,
    }


def estimate_review(
    job: dict[str, Any],
    settings: LlmSettings,
    *,
    max_chunks: int = 0,
    sample_chunks: int = 0,
    mode: str = "report",
) -> dict[str, Any]:
    if mode not in ESTIMATE_OUTPUT_TOKENS:
        raise ValueError("mode 必须是 report 或 patch")
    plan = plan_review(
        job,
        settings.max_chars,
        max_chunks=max_chunks,
        sample_chunks=sample_chunks,
    )
    prompt_tokens = (
        int(plan.selected_chars * ESTIMATE_TOKENS_PER_CHAR)
        + ESTIMATE_PROMPT_OVERHEAD_TOKENS * plan.selected_chunks
    )
    completion_tokens = ESTIMATE_OUTPUT_TOKENS[mode] * plan.selected_chunks
    return {
        "mode": mode,
        "settings": {
            "model": settings.model,
            "profile": settings.profile_name,
            "maxChars": settings.max_chars,
            "thinking": settings.thinking,
        },
        "plannedChunks": plan.planned_chunks,
        "selectedChunks": plan.selected_chunks,
        "sample": plan.sample,
        "plannedChars": plan.planned_chars,
        "selectedChars": plan.selected_chars,
        "estimated": {
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": prompt_tokens + completion_tokens,
        },
        "cost": _estimate_cost(prompt_tokens, completion_tokens, settings.pricing),
    }


def _count_glossary_terms(path: Path | None) -> int:
    if path is None or not path.is_file():
        return 0
    terms = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms += 1
    return terms


def describe_profiles(config_file: Path | None = None) -> list[dict[str, Any]]:
    config = _read_json(config_file or DEFAULT_CONFIG_FILE)
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
    names = [""] + sorted(
        name for name, data in profiles.items() if isinstance(data, dict)
    )

    result: list[dict[str, Any]] = []
    for name in names:
        settings = load_settings(
            profile=name or None,
            strict_profile=bool(name),
            config_file=config_file,
        )
        result.append(
            {
                "name": name or "-",
                "model": settings.model,
                "baseUrl": settings.base_url,
                "maxChars": settings.max_chars,
                "maxTokens": settings.max_tokens,
                "thinking": settings.thinking,
                "temperature": settings.temperature,
                "minConfidence": settings.min_confidence,
                "glossary": str(settings.glossary_file) if settings.glossary_file else "",
                "glossaryTerms": _count_glossary_terms(settings.glossary_file),
                "style": settings.style,
                "keyConfigured": settings.enabled,
                "keyFile": str(settings.key_file),
            }
        )
    return result


def _extract_json(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:])
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("LLM 返回中没有 JSON 对象")
    return text[start : end + 1]


def _normalise_type(value: Any) -> str:
    issue_type = str(value or "other").strip().lower()
    return issue_type if issue_type in ALLOWED_ISSUE_TYPES else "other"


def _normalise_confidence(value: Any, default: str) -> str:
    confidence = str(value or default).strip().lower()
    return confidence if confidence in {"high", "medium", "low"} else default


def parse_issues(content: str) -> list[dict[str, str]]:
    data = json.loads(_extract_json(content))
    if not isinstance(data, dict):
        raise ValueError("LLM JSON 根节点必须是对象")
    raw_issues = data.get("issues")
    if not isinstance(raw_issues, list):
        raise ValueError("LLM JSON 缺少 issues 数组")

    issues: list[dict[str, str]] = []
    for item in raw_issues[:MAX_ISSUES_PER_CHUNK]:
        if not isinstance(item, dict):
            continue
        excerpt = str(item.get("excerpt", "")).strip()[:80]
        message = str(item.get("message", "")).strip()[:200]
        suggestion = str(item.get("suggestion", "")).strip()[:200]
        if not excerpt and not message:
            continue
        issues.append(
            {
                "type": _normalise_type(item.get("type")),
                "excerpt": excerpt,
                "message": message,
                "suggestion": suggestion,
                "confidence": _normalise_confidence(item.get("confidence"), "medium"),
            }
        )
    return issues


def parse_patches(content: str) -> list[dict[str, str]]:
    data = json.loads(_extract_json(content))
    if not isinstance(data, dict):
        raise ValueError("LLM JSON 根节点必须是对象")
    raw_issues = data.get("issues")
    if not isinstance(raw_issues, list):
        raise ValueError("LLM JSON 缺少 issues 数组")

    patches: list[dict[str, str]] = []
    for item in raw_issues[:MAX_ISSUES_PER_CHUNK]:
        if not isinstance(item, dict):
            continue
        find = str(item.get("find", ""))
        replace = str(item.get("replace", ""))
        if not find.strip() or find == replace or len(find) > 200:
            continue
        patches.append(
            {
                "type": _normalise_type(item.get("type")),
                "find": find,
                "replace": replace[:400],
                "reason": str(item.get("reason", "")).strip()[:200],
                "confidence": _normalise_confidence(item.get("confidence"), "low"),
            }
        )
    return patches


def build_user_prompt(
    chapter: str,
    text: str,
    *,
    mode: str = "report",
    glossary: list[str] | None = None,
) -> str:
    label = chapter.strip() or "正文"
    glossary_line = ""
    if glossary:
        glossary_line = "术语表（不得修改）：" + "、".join(glossary) + "\n"

    if mode == "patch":
        return (
            f"章节：{label}\n"
            f"{glossary_line}"
            "<target>\n"
            f"{text}\n"
            "</target>\n"
            "只允许修改 <target> 内的文字；上下文与术语不得修改；"
            "找不到明确错误就不要输出补丁。"
        )

    return f"章节：{label}\n{glossary_line}请核验以下正文：\n---\n{text}\n---"


def review_job(
    job: dict[str, Any],
    settings: LlmSettings,
    *,
    job_path: str | Path | None = None,
    max_chunks: int = 0,
    sample_chunks: int = 0,
    client: ChatClient | None = None,
    max_errors: int = 3,
    mode: str = "report",
    glossary: list[str] | None = None,
    progress: Callable[[int, int, str], None] | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    if mode not in {"report", "patch"}:
        raise ValueError("mode 必须是 report 或 patch")
    if sample_chunks < 0:
        raise ValueError("sample_chunks 不能小于 0")

    segments = job.get("segments") if isinstance(job.get("segments"), list) else []
    plan = plan_review(
        job,
        settings.max_chars,
        max_chunks=max_chunks,
        sample_chunks=sample_chunks,
    )
    planned_chunks = plan.planned_chunks

    report: dict[str, Any] = {
        "version": 1,
        "mode": mode,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "job": str(job_path) if job_path else "",
            "titleBase": job.get("titleBase", ""),
            "sourceHash": job.get("sourceHash", ""),
            "segments": len(segments),
        },
        "settings": {
            "baseUrl": settings.base_url,
            "model": settings.model,
            "maxChars": settings.max_chars,
            "temperature": settings.temperature,
            "maxTokens": settings.max_tokens,
            "thinking": settings.thinking,
            "profile": settings.profile_name,
            "style": settings.style,
        },
        "policy": {
            "minConfidence": settings.min_confidence,
            "maxDelta": settings.max_delta,
        },
        "summary": {
            "segments": len(segments),
            "plannedChunks": planned_chunks,
            "chunks": 0,
            "sample": 0,
            "selectedChunks": 0,
            "issues": 0,
            "errors": 0,
            "blocked": 0,
            "skipped": not settings.enabled,
            "cancelled": False,
        },
        "issues": [],
        "errors": [],
        "blocked": [],
        "usage": {
            "promptTokens": 0,
            "completionTokens": 0,
            "reasoningTokens": 0,
            "totalTokens": 0,
        },
    }

    if not settings.enabled:
        report["summary"]["reason"] = "未配置 LLM API key"
        return report

    chat_client = client or OpenAiCompatibleClient(settings)
    style_suffix = f"\n【本书特定要求】{settings.style}" if settings.style else ""
    system_prompt = (
        (SYSTEM_PROMPT_PATCH if mode == "patch" else SYSTEM_PROMPT_REPORT)
        + style_suffix
    )
    parser = parse_patches if mode == "patch" else parse_issues

    issues: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    usage_totals = report["usage"]
    processed_chunks = 0
    stopped = False

    report["summary"]["plannedChunks"] = plan.planned_chunks
    report["summary"]["sample"] = plan.sample
    report["summary"]["selectedChunks"] = plan.selected_chunks

    for item in plan.chunks:
        if cancel is not None and cancel.is_set():
            break
        if len(issues) >= MAX_REPORT_ISSUES:
            stopped = True
            break

        processed_chunks += 1
        segment_index = item["segment"]
        chapter = item["chapter"]
        chunk_index = item["chunk"]
        chunk_start = item["chunkStart"]
        chunk_end = item["chunkEnd"]
        chunk = item["text"]
        try:
            content = chat_client.complete(
                system_prompt,
                build_user_prompt(chapter, chunk, mode=mode, glossary=glossary),
            )
            usage = getattr(chat_client, "last_usage", None)
            if isinstance(usage, dict):
                usage_totals["promptTokens"] += int(usage.get("prompt_tokens", 0) or 0)
                usage_totals["completionTokens"] += int(
                    usage.get("completion_tokens", 0) or 0
                )
                usage_totals["totalTokens"] += int(usage.get("total_tokens", 0) or 0)
                details = usage.get("completion_tokens_details")
                if isinstance(details, dict):
                    usage_totals["reasoningTokens"] += int(
                        details.get("reasoning_tokens", 0) or 0
                    )
            found = parser(content)
            chunk_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
            for issue in found:
                issues.append(
                    {
                        **issue,
                        "segment": segment_index,
                        "chapter": chapter,
                        "chunk": chunk_index,
                        "chunkStart": chunk_start,
                        "chunkEnd": chunk_end,
                        "chunkHash": chunk_hash,
                    }
                )
        except LlmBlockedError as error:
            blocked.append(
                {
                    "segment": segment_index,
                    "chapter": chapter,
                    "chunk": chunk_index,
                    "message": str(error),
                }
            )
            continue
        except LlmError as error:
            errors.append(
                {
                    "segment": segment_index,
                    "chapter": chapter,
                    "chunk": chunk_index,
                    "message": str(error),
                }
            )
            stopped = True
            break
        except ValueError as error:
            errors.append(
                {
                    "segment": segment_index,
                    "chapter": chapter,
                    "chunk": chunk_index,
                    "message": str(error),
                }
            )
            if len(errors) >= max_errors:
                stopped = True
                break
        finally:
            if progress is not None:
                progress(
                    processed_chunks,
                    plan.selected_chunks,
                    f"{chapter} #{chunk_index}",
                )

    cancelled = cancel is not None and cancel.is_set()
    report["summary"]["cancelled"] = cancelled
    report["summary"]["chunks"] = processed_chunks
    report["summary"]["issues"] = len(issues)
    report["summary"]["errors"] = len(errors)
    report["summary"]["blocked"] = len(blocked)
    report["summary"]["limited"] = bool(
        cancelled
        or plan.selected_chunks < plan.planned_chunks
        or processed_chunks < plan.selected_chunks
    )
    report["issues"] = issues[:MAX_REPORT_ISSUES]
    report["errors"] = errors
    report["blocked"] = blocked
    return report


def write_report(report: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination
