from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .llm import (
    BOOKFORGE_ROOT,
    DEFAULT_CONFIG_FILE,
    DEFAULT_KEY_FILE,
    OpenAiCompatibleClient,
    load_settings,
)

KEY_ENV = "BOOKFORGE_LLM_KEY_FILE"
MAX_KEY_LENGTH = 4096


@dataclass(frozen=True)
class KeyStatus:
    configured: bool
    source: str
    path: Path
    masked: str
    env_override: bool


def _read_config(path: Path | None) -> dict:
    target = path or DEFAULT_CONFIG_FILE
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BOOKFORGE_ROOT / path


def resolve_key_path(
    profile: str | None = None,
    config_file: Path | None = None,
) -> tuple[Path, str, bool]:
    """返回 (key 文件路径, 来源, 是否被环境变量覆盖)。

    优先级与 llm.load_settings 一致：环境变量 > profile.key_file > 全局 key_file > 默认文件。
    """
    env_value = os.environ.get(KEY_ENV)
    if env_value:
        return _resolve_path(env_value), "env", True

    config = _read_config(config_file)
    if profile:
        profiles = config.get("profiles")
        data = profiles.get(profile) if isinstance(profiles, dict) else None
        if isinstance(data, dict) and data.get("key_file"):
            return _resolve_path(str(data["key_file"])), "profile", False
    if config.get("key_file"):
        return _resolve_path(str(config["key_file"])), "config", False
    return DEFAULT_KEY_FILE, "default", False


def validate_key(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("API key 不能为空")
    if len(text) > MAX_KEY_LENGTH:
        raise ValueError(f"API key 过长（上限 {MAX_KEY_LENGTH} 字符）")
    if any(char in text for char in "\r\n\t"):
        raise ValueError("API key 不能包含换行或制表符")
    return text


def read_key(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip().strip('"').strip("'")


def mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) < 12:
        return "****"
    return f"{value[:4]}…{value[-4:]}"


def key_status(
    profile: str | None = None,
    config_file: Path | None = None,
) -> KeyStatus:
    path, source, env_override = resolve_key_path(profile, config_file)
    value = read_key(path)
    return KeyStatus(
        configured=bool(value),
        source=source,
        path=path,
        masked=mask_key(value),
        env_override=env_override,
    )


def source_label(status: KeyStatus) -> str:
    return {
        "env": f"环境变量 {KEY_ENV}",
        "profile": "profile.key_file",
        "config": "全局 key_file",
        "default": "默认文件",
    }.get(status.source, status.source)


def save_key(
    value: str,
    profile: str | None = None,
    config_file: Path | None = None,
) -> Path:
    cleaned = validate_key(value)
    path, _source, _env = resolve_key_path(profile, config_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(cleaned + "\n", encoding="utf-8")
    os.replace(temp, path)
    _restrict_permissions(path)
    return path


def clear_key(
    profile: str | None = None,
    config_file: Path | None = None,
) -> tuple[Path, bool]:
    path, _source, _env = resolve_key_path(profile, config_file)
    if path.is_file():
        path.unlink()
        return path, True
    return path, False


def test_connection(
    profile: str | None = None,
    config_file: Path | None = None,
) -> str:
    settings = load_settings(
        profile=profile or None,
        strict_profile=bool(profile),
        config_file=config_file,
    )
    if not settings.enabled:
        raise ValueError(f"未配置 API key（{settings.key_file}）")
    client = OpenAiCompatibleClient(settings)
    return client.complete("你是连接测试助手。", "只回复 OK。").strip()[:200]


def _restrict_permissions(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
