from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from bookforge import cli
from bookforge.keymanagement import (
    DEFAULT_KEY_FILE,
    KEY_ENV,
    clear_key,
    key_status,
    mask_key,
    read_key,
    resolve_key_path,
    save_key,
    validate_key,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KEY_ENV, raising=False)


def test_default_key_path() -> None:
    path, source, overridden = resolve_key_path()

    assert path == DEFAULT_KEY_FILE
    assert source == "default"
    assert overridden is False


def test_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "env-key.txt"
    monkeypatch.setenv(KEY_ENV, str(target))

    path, source, overridden = resolve_key_path()

    assert path == target
    assert source == "env"
    assert overridden is True


def test_profile_key_file(tmp_path: Path) -> None:
    target = tmp_path / "book-key.txt"
    config_file = tmp_path / "llm_config.json"
    config_file.write_text(
        json.dumps({"profiles": {"三体1": {"key_file": str(target)}}}),
        encoding="utf-8",
    )

    path, source, _ = resolve_key_path("三体1", config_file)

    assert path == target
    assert source == "profile"


def test_save_read_mask_and_clear(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "key.txt"
    monkeypatch.setenv(KEY_ENV, str(target))

    written = save_key("  sk-1234567890abcdef  ")
    assert written == target
    assert read_key(target) == "sk-1234567890abcdef"

    status = key_status()
    assert status.configured is True
    assert status.source == "env"
    assert status.env_override is True
    assert "sk-1234567890abcdef" not in status.masked

    cleaned = validate_key(" sk-test-1234567890 ")
    assert cleaned == "sk-test-1234567890"
    assert mask_key(cleaned) == "sk-t…7890"
    assert mask_key("short") == "****"

    path, removed = clear_key()
    assert removed is True
    assert not path.exists()


def test_save_profile_key_and_clear(tmp_path: Path) -> None:
    target = tmp_path / "book-key.txt"
    config_file = tmp_path / "llm_config.json"
    config_file.write_text(json.dumps({"key_file": str(target)}), encoding="utf-8")

    saved = save_key("sk-book-key-123456", config_file=config_file)
    assert saved == target

    status = key_status(config_file=config_file)
    assert status.configured is True
    assert status.source == "config"
    assert "sk-book-key-123456" not in status.masked

    path, removed = clear_key(config_file=config_file)
    assert removed is True
    assert not path.exists()


def test_rejects_invalid_key() -> None:
    with pytest.raises(ValueError):
        validate_key("   ")
    with pytest.raises(ValueError):
        validate_key("sk-test\nsecond-line")
    with pytest.raises(ValueError):
        validate_key("x" * 5000)


def test_cli_key_set_status_and_clear(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "cli-key.txt"
    config_file = tmp_path / "llm_config.json"
    config_file.write_text(json.dumps({"key_file": str(target)}), encoding="utf-8")

    stdin = type("FakeStdin", (), {"isatty": lambda self: False, "readline": lambda self: "sk-cli-secret-123456\n"})()
    monkeypatch.setattr(sys, "stdin", stdin)

    monkeypatch.setattr(sys, "argv", ["bookforge", "key", "set", "--config", str(config_file)])
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert "sk-cli-secret-123456" not in output

    assert read_key(target) == "sk-cli-secret-123456"

    monkeypatch.setattr(sys, "argv", ["bookforge", "key", "status", "--config", str(config_file)])
    assert cli.main() == 0
    status = capsys.readouterr().out
    assert "configured" in status
    assert "sk-c…3456" in status
    assert "sk-cli-secret-123456" not in status

    monkeypatch.setattr(sys, "argv", ["bookforge", "key", "clear", "--config", str(config_file)])
    assert cli.main() == 0
    assert "removed" in capsys.readouterr().out
    assert not target.exists()
