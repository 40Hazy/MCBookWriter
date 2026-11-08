from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from bookforge.gui.models import IssueTableModel

APP = QApplication.instance() or QApplication([])


def test_patch_model_checks_high_confidence_by_default() -> None:
    model = IssueTableModel()
    model.set_issues(
        [
            {"type": "typo", "confidence": "high", "find": "错", "replace": "对"},
            {"type": "missing", "confidence": "medium", "find": "缺", "replace": "补"},
        ],
        "patch",
    )

    selected = model.selected_issues()

    assert len(selected) == 1
    assert selected[0]["confidence"] == "high"
    assert model.columnCount() == 8


def test_patch_model_toggle_selection() -> None:
    model = IssueTableModel()
    model.set_issues(
        [{"type": "typo", "confidence": "high", "find": "错", "replace": "对"}],
        "patch",
    )

    model.clear_checks()
    assert model.selected_issues() == []

    index = model.index(0, 0)
    model.setData(index, 2, 10)
    assert len(model.selected_issues()) == 1


def test_report_model_headers_and_values() -> None:
    model = IssueTableModel()
    model.set_issues(
        [
            {
                "segment": 1,
                "chapter": "第一章",
                "chunk": 2,
                "type": "typo",
                "confidence": "high",
                "excerpt": "原文",
                "message": "说明",
                "suggestion": "建议",
            }
        ],
        "report",
    )

    assert model.columnCount() == 8
    assert model.data(model.index(0, 5)) == "原文"
    assert model.data(model.index(0, 6)) == "说明"
