from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..keymanagement import (
    clear_key as clear_key_file,
    key_status as api_key_status,
    save_key as save_key_file,
    source_label,
)
from ..linkage import install_job
from ..llm import BOOKFORGE_ROOT, DEFAULT_CONFIG_FILE, OpenAiCompatibleClient, load_settings

PROFILE_FIELDS = (
    "model",
    "base_url",
    "max_chars",
    "max_tokens",
    "temperature",
    "thinking",
    "min_confidence",
    "glossary",
    "style",
    "key_file",
)


def read_config(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_CONFIG_FILE
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_config(config: dict[str, Any], path: Path | None = None) -> Path:
    target = path or DEFAULT_CONFIG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def profile_names(config: dict[str, Any]) -> list[str]:
    profiles = config.get("profiles")
    names = [""]
    if isinstance(profiles, dict):
        names.extend(sorted(str(name) for name in profiles if isinstance(profiles[name], dict)))
    return names


def profile_label(name: str) -> str:
    return name or "全局"


def profile_values(config: dict[str, Any], name: str) -> dict[str, Any]:
    base = {
        "model": config.get("model", "deepseek-flash"),
        "base_url": config.get("base_url", "https://api.deepseek.com"),
        "max_chars": config.get("max_chars", 4000),
        "max_tokens": config.get("max_tokens", 8192),
        "temperature": config.get("temperature", 0),
        "thinking": config.get("thinking", False),
        "min_confidence": config.get("min_confidence", "high"),
        "glossary": config.get("glossary", "keys/glossary.txt"),
        "style": "",
        "key_file": config.get("key_file", ""),
    }
    profiles = config.get("profiles")
    if name and isinstance(profiles, dict) and isinstance(profiles.get(name), dict):
        base.update(profiles[name])
    return base


def save_profile(
    config: dict[str, Any],
    name: str,
    values: dict[str, Any],
    path: Path | None = None,
) -> Path:
    if name:
        profiles = config.setdefault("profiles", {})
        if not isinstance(profiles, dict):
            profiles = {}
            config["profiles"] = profiles
        profile = profiles.setdefault(name, {})
        if not isinstance(profile, dict):
            profile = {}
            profiles[name] = profile
        for key in PROFILE_FIELDS:
            if key not in values:
                continue
            if key == "key_file" and not values[key]:
                profile.pop("key_file", None)
            else:
                profile[key] = values[key]
    else:
        for key in PROFILE_FIELDS:
            if key not in values:
                continue
            if key == "key_file" and not values[key]:
                config.pop("key_file", None)
            else:
                config[key] = values[key]
    return write_config(config, path)


def key_status(
    profile: str = "",
    config_file: Path | None = None,
) -> str:
    status = api_key_status(profile or None, config_file)
    label = f"已配置 {status.masked}" if status.configured else "未配置"
    return f"{label}（{source_label(status)}：{status.path}）"


def save_api_key(
    value: str,
    profile: str = "",
    config_file: Path | None = None,
) -> Path:
    return save_key_file(value, profile or None, config_file)


def clear_api_key(
    profile: str = "",
    config_file: Path | None = None,
) -> tuple[Path, bool]:
    return clear_key_file(profile or None, config_file)


def glossary_count(value: str) -> int:
    if not value:
        return 0
    path = Path(value)
    if not path.is_absolute():
        path = BOOKFORGE_ROOT / path
    if not path.is_file():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def test_connection(settings) -> str:
    client = OpenAiCompatibleClient(settings)
    content = client.complete("你是连接测试助手。", "只回复 OK。")
    return content.strip()[:200]


def load_test_settings(name: str):
    return load_settings(profile=name or None, strict_profile=bool(name))
