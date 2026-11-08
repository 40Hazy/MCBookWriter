from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

REPORT_HEADERS = ("段", "章节", "块", "类型", "置信度", "原文", "说明", "建议")
PATCH_HEADERS = ("选择", "段", "块", "类型", "置信度", "查找", "替换", "原因")


class IssueTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._issues: list[dict[str, Any]] = []
        self._mode = "report"
        self._checked: set[int] = set()

    @property
    def mode(self) -> str:
        return self._mode

    def set_issues(self, issues: list[dict[str, Any]], mode: str) -> None:
        self.beginResetModel()
        self._issues = [item for item in issues if isinstance(item, dict)]
        self._mode = "patch" if mode == "patch" else "report"
        self._checked = {
            index
            for index, item in enumerate(self._issues)
            if self._mode == "patch"
            and str(item.get("confidence", "low")).lower() == "high"
        }
        self.endResetModel()

    def issues(self) -> list[dict[str, Any]]:
        return list(self._issues)

    def selected_issues(self) -> list[dict[str, Any]]:
        if self._mode != "patch":
            return []
        return [self._issues[index] for index in sorted(self._checked)]

    def set_all_high_confidence(self) -> None:
        self._checked = {
            index
            for index, item in enumerate(self._issues)
            if str(item.get("confidence", "low")).lower() == "high"
        }
        if self._issues:
            top = self.index(0, 0)
            bottom = self.index(len(self._issues) - 1, 0)
            self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.CheckStateRole])

    def clear_checks(self) -> None:
        self._checked.clear()
        if self._issues:
            top = self.index(0, 0)
            bottom = self.index(len(self._issues) - 1, 0)
            self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.CheckStateRole])

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._issues)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(PATCH_HEADERS if self._mode == "patch" else REPORT_HEADERS)

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation != Qt.Orientation.Horizontal:
            return section + 1
        headers = PATCH_HEADERS if self._mode == "patch" else REPORT_HEADERS
        return headers[section] if 0 <= section < len(headers) else None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._issues):
            return None
        issue = self._issues[index.row()]
        column = index.column()
        if self._mode == "patch":
            if column == 0 and role == Qt.ItemDataRole.CheckStateRole:
                return (
                    Qt.CheckState.Checked
                    if index.row() in self._checked
                    else Qt.CheckState.Unchecked
                )
            values = (
                None,
                issue.get("segment"),
                issue.get("chunk"),
                issue.get("type"),
                issue.get("confidence"),
                issue.get("find"),
                issue.get("replace"),
                issue.get("reason"),
            )
        else:
            values = (
                issue.get("segment"),
                issue.get("chapter"),
                issue.get("chunk"),
                issue.get("type"),
                issue.get("confidence"),
                issue.get("excerpt"),
                issue.get("message"),
                issue.get("suggestion"),
            )
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        return "" if values[column] is None else str(values[column])

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)
        if self._mode == "patch" and index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if (
            not index.isValid()
            or self._mode != "patch"
            or index.column() != 0
            or role != Qt.ItemDataRole.CheckStateRole
        ):
            return False
        row = index.row()
        if value == Qt.CheckState.Checked or value == Qt.CheckState.Checked.value:
            self._checked.add(row)
        else:
            self._checked.discard(row)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        return True
