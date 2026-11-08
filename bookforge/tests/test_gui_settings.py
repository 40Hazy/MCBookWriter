from __future__ import annotations

import json
from pathlib import Path

from bookforge.gui.settings import (
    install_job,
    profile_names,
    profile_values,
    read_config,
    save_profile,
)


def test_profile_names_and_values(tmp_path: Path) -> None:
    config_file = tmp_path / "llm_config.json"
    config_file.write_text(
        json.dumps(
            {
                "model": "global-model",
                "base_url": "https://global.example/v1",
                "max_chars": 4000,
                "profiles": {
                    "三体1": {
                        "model": "book-model",
                        "max_chars": 2500,
                        "thinking": False,
                        "style": "保留科幻术语",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    config = read_config(config_file)
    assert profile_names(config) == ["", "三体1"]
    assert profile_values(config, "")["model"] == "global-model"

    values = profile_values(config, "三体1")
    assert values["model"] == "book-model"
    assert values["max_chars"] == 2500
    assert values["style"] == "保留科幻术语"


def test_save_profile_updates_named_profile(tmp_path: Path) -> None:
    config_file = tmp_path / "llm_config.json"
    config_file.write_text(json.dumps({"model": "global", "profiles": {"三体1": {}}}), encoding="utf-8")

    config = read_config(config_file)
    save_profile(
        config,
        "三体1",
        {
            "model": "new-model",
            "max_chars": 3000,
            "max_tokens": 8192,
            "temperature": 0,
            "thinking": False,
            "min_confidence": "high",
            "glossary": "keys/glossary.txt",
            "style": "保留术语",
            "base_url": "https://api.example",
        },
        config_file,
    )

    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved["profiles"]["三体1"]["model"] == "new-model"
    assert saved["profiles"]["三体1"]["max_chars"] == 3000
    assert saved["profiles"]["三体1"]["style"] == "保留术语"


def test_profile_key_file_roundtrip(tmp_path: Path) -> None:
    config_file = tmp_path / "llm_config.json"
    config_file.write_text(
        json.dumps({"key_file": "keys/global-key.txt", "profiles": {"三体1": {}}}),
        encoding="utf-8",
    )

    config = read_config(config_file)
    assert profile_values(config, "三体1")["key_file"] == "keys/global-key.txt"

    save_profile(
        config,
        "三体1",
        {"key_file": "keys/book-key.txt", "model": "book-model"},
        config_file,
    )
    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved["profiles"]["三体1"]["key_file"] == "keys/book-key.txt"

    save_profile(config, "三体1", {"key_file": "", "model": "book-model"}, config_file)
    saved = json.loads(config_file.read_text(encoding="utf-8"))
    assert "key_file" not in saved["profiles"]["三体1"]


def test_install_job_uses_title_base(tmp_path: Path) -> None:
    job_file = tmp_path / "job.json"
    job_file.write_text(
        json.dumps({"version": 1, "titleBase": "三体1", "segments": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    game_dir = tmp_path / "game"

    destination = install_job(job_file, game_dir)

    assert destination == game_dir / "autobook" / "jobs" / "三体1.json"
    assert destination.is_file()
    assert json.loads(destination.read_text(encoding="utf-8"))["titleBase"] == "三体1"
