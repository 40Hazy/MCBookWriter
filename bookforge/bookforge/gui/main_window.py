from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableView,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..llm import BOOKFORGE_ROOT, load_settings
from ..manifest import validate_job_data
from .help_content import build_help_html
from .models import IssueTableModel
from .settings import (
    clear_api_key,
    install_job,
    key_status,
    profile_label,
    profile_names,
    profile_values,
    read_config,
    save_api_key,
    save_profile,
)
from .workers import ApplyWorker, ConnectionWorker, PrepareWorker, ReviewWorker


def _read_glossary(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line)
    return list(dict.fromkeys(terms))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BookForge")
        self._prepare_worker: PrepareWorker | None = None
        self._review_worker: ReviewWorker | None = None
        self._apply_worker: ApplyWorker | None = None
        self._connection_worker: ConnectionWorker | None = None
        self._job: dict[str, Any] | None = None
        self._job_path: Path | None = None
        self._patch_report: dict[str, Any] | None = None
        self._patch_path: Path | None = None

        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        self.setCentralWidget(central)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_prepare_tab(), "生成")
        self.tabs.addTab(self._build_review_tab(), "LLM 核验")
        self.tabs.addTab(self._build_patch_tab(), "补丁审阅")
        self.tabs.addTab(self._build_config_tab(), "配置")
        self.tabs.addTab(self._build_help_tab(), "帮助")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, 1)

        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        log_layout.addWidget(self.log_view)
        root.addWidget(log_group, 0)

        self._ui_settings = QSettings("MCBookWriter", "BookForge")
        self._restore_paths()
        self._reload_profiles()

    # ---------- tabs ----------

    def _build_prepare_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form_group = QGroupBox("书稿")
        form = QFormLayout(form_group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.input_edit = QLineEdit()
        self.input_edit.setToolTip(
            "支持 .txt/.md/.epub/.fb2/.docx/.azw3/.mobi 等无 DRM 格式。"
        )
        self.input_button = QPushButton("浏览")
        form.addRow("输入文件", self._row(self.input_edit, self.input_button))

        self.output_edit = QLineEdit()
        self.output_edit.setToolTip("留空时默认为 work\\<输入文件名>。")
        self.output_button = QPushButton("浏览")
        form.addRow("输出目录", self._row(self.output_edit, self.output_button))

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("留空时使用电子书元数据或文件名")
        self.title_edit.setToolTip("书名基名，最长 24 字符；游戏内书名按此编号。")
        form.addRow("书名", self.title_edit)

        self.page_limit_spin = QSpinBox()
        self.page_limit_spin.setRange(1, 100)
        self.page_limit_spin.setValue(100)
        self.page_limit_spin.setToolTip("每本成书的最大页数（1–100）。")
        self.max_chars_spin = QSpinBox()
        self.max_chars_spin.setRange(500, 200000)
        self.max_chars_spin.setSingleStep(1000)
        self.max_chars_spin.setValue(12000)
        self.max_chars_spin.setToolTip("单个分段的最大字符数；也影响 LLM 核验的分块。")
        settings_row = QWidget()
        settings_layout = QHBoxLayout(settings_row)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.addWidget(QLabel("每本页数"))
        settings_layout.addWidget(self.page_limit_spin)
        settings_layout.addSpacing(18)
        settings_layout.addWidget(QLabel("单段最大字符"))
        settings_layout.addWidget(self.max_chars_spin)
        settings_layout.addStretch(1)
        form.addRow("生成参数", settings_row)

        self.prepare_button = QPushButton("导入并生成 job")
        self.prepare_button.setMinimumHeight(32)
        self.prepare_button.setToolTip(
            "读取书稿并生成 job.json / report.json；电子书会同时生成 import.json。"
        )
        form.addRow("", self.prepare_button)
        layout.addWidget(form_group)

        summary_group = QGroupBox("结果")
        summary_layout = QVBoxLayout(summary_group)
        self.summary_label = QLabel("尚未生成。")
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        summary_layout.addWidget(self.summary_label)
        summary_layout.addWidget(self.progress)
        layout.addWidget(summary_group)
        layout.addStretch(1)

        self.input_button.clicked.connect(self._browse_input)
        self.output_button.clicked.connect(self._browse_output)
        self.prepare_button.clicked.connect(self._prepare)
        return widget

    def _build_review_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        self.review_job_edit = QLineEdit()
        self.review_job_edit.setToolTip("生成页产出的 job.json；会按书名自动匹配 profile。")
        self.review_job_button = QPushButton("浏览")
        form.addRow("job.json", self._row(self.review_job_edit, self.review_job_button))

        self.review_mode = QComboBox()
        self.review_mode.addItem("问题报告", "report")
        self.review_mode.addItem("补丁", "patch")
        self.review_mode.setToolTip(
            "report：只列出问题；patch：生成 find/replace 补丁（不自动改动正文）。"
        )
        self.review_sample = QSpinBox()
        self.review_sample.setRange(0, 500)
        self.review_sample.setSpecialValueText("全量")
        self.review_sample.setToolTip("从全书均匀抽取 N 个块先试跑；0 表示全量。")
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.review_mode)
        row_layout.addSpacing(16)
        row_layout.addWidget(QLabel("抽样块数"))
        row_layout.addWidget(self.review_sample)
        row_layout.addStretch(1)
        form.addRow("模式", row)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.review_start_button = QPushButton("开始核验")
        self.review_start_button.setToolTip(
            "调用配置的 LLM 服务核验；未配置 API key 时会跳过并生成跳过报告。"
        )
        self.review_cancel_button = QPushButton("取消")
        self.review_cancel_button.setEnabled(False)
        buttons.addWidget(self.review_start_button)
        buttons.addWidget(self.review_cancel_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.review_progress = QProgressBar()
        self.review_progress.setRange(0, 1)
        self.review_progress.setValue(0)
        self.review_summary = QLabel("尚未核验。")
        self.review_summary.setWordWrap(True)
        layout.addWidget(self.review_progress)
        layout.addWidget(self.review_summary)

        self.review_model = IssueTableModel(self)
        self.review_table = QTableView()
        self.review_table.setModel(self.review_model)
        self.review_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.review_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.review_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.review_table, 1)

        self.review_job_button.clicked.connect(self._browse_review_job)
        self.review_start_button.clicked.connect(self._start_review)
        self.review_cancel_button.clicked.connect(self._cancel_review)
        return widget

    def _build_patch_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        self.patch_path_edit = QLineEdit()
        self.patch_path_edit.setToolTip("LLM 核验“补丁”模式生成的 llm_patch.json。")
        self.patch_path_button = QPushButton("浏览")
        form.addRow("patch.json", self._row(self.patch_path_edit, self.patch_path_button))
        self.patch_load_button = QPushButton("加载补丁")
        self.patch_load_button.setToolTip("读取补丁文件，默认勾选 high 置信度条目。")
        form.addRow("", self.patch_load_button)

        buttons = QHBoxLayout()
        self.patch_high_button = QPushButton("仅勾选高置信度")
        self.patch_high_button.setToolTip("只保留 high 置信度条目的勾选。")
        self.patch_clear_button = QPushButton("清空勾选")
        self.patch_apply_button = QPushButton("应用选中补丁")
        self.patch_apply_button.setToolTip(
            "本地硬校验后应用到 job，输出 reviewed/job.json、diff.patch 与 patch_apply.json。"
        )
        buttons.addWidget(self.patch_high_button)
        buttons.addWidget(self.patch_clear_button)
        buttons.addWidget(self.patch_apply_button)
        buttons.addStretch(1)
        layout.addLayout(form)
        layout.addLayout(buttons)

        self.patch_out_edit = QLineEdit()
        self.patch_out_edit.setToolTip("reviewed 输出目录，默认在 patch 文件旁的 reviewed\\。")
        self.patch_out_button = QPushButton("浏览")
        out_row = QWidget()
        out_layout = QHBoxLayout(out_row)
        out_layout.setContentsMargins(0, 0, 0, 0)
        out_layout.addWidget(QLabel("输出目录"))
        out_layout.addWidget(self.patch_out_edit, 1)
        out_layout.addWidget(self.patch_out_button)
        layout.addWidget(out_row)

        self.patch_model = IssueTableModel(self)
        self.patch_table = QTableView()
        self.patch_table.setModel(self.patch_model)
        self.patch_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.patch_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.patch_table.horizontalHeader().setStretchLastSection(True)
        self.patch_table.setMinimumHeight(160)
        layout.addWidget(self.patch_table, 1)

        self.patch_status = QLabel("尚未加载补丁。")
        self.patch_status.setWordWrap(True)
        layout.addWidget(self.patch_status)

        diff_group = QGroupBox("diff 预览")
        diff_layout = QVBoxLayout(diff_group)
        self.diff_view = QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(QFont("Consolas", 9))
        self.diff_view.setMinimumHeight(260)
        diff_layout.addWidget(self.diff_view)
        layout.addWidget(diff_group, 2)

        rejected_group = QGroupBox("被拒绝的补丁")
        rejected_layout = QVBoxLayout(rejected_group)
        self.rejected_view = QPlainTextEdit()
        self.rejected_view.setReadOnly(True)
        self.rejected_view.setMinimumHeight(110)
        rejected_layout.addWidget(self.rejected_view)
        layout.addWidget(rejected_group, 1)

        self.patch_path_button.clicked.connect(self._browse_patch)
        self.patch_load_button.clicked.connect(self._load_patch)
        self.patch_high_button.clicked.connect(
            lambda: self.patch_model.set_all_high_confidence()
        )
        self.patch_clear_button.clicked.connect(self.patch_model.clear_checks)
        self.patch_apply_button.clicked.connect(self._apply_patch)
        self.patch_out_button.clicked.connect(self._browse_patch_out)
        return widget

    def _build_config_tab(self) -> QWidget:
        widget = QWidget()
        self._config_tab = widget
        layout = QVBoxLayout(widget)

        profile_group = QGroupBox("LLM profile")
        profile_layout = QFormLayout(profile_group)
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip("“全局”适用于所有书；按书名建立的 profile 会覆盖全局设置。")
        profile_layout.addRow("选择", self.profile_combo)
        self.profile_key_label = QLabel()
        self.profile_key_label.setWordWrap(True)
        profile_layout.addRow("API key", self.profile_key_label)

        self.model_edit = QLineEdit()
        self.model_edit.setToolTip("模型名，如 deepseek-flash；换服务商时同步修改 base_url。")
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setToolTip("OpenAI 兼容服务的根地址，如 https://api.deepseek.com。")
        self.cfg_max_chars = QSpinBox()
        self.cfg_max_chars.setRange(200, 200000)
        self.cfg_max_chars.setSingleStep(500)
        self.cfg_max_chars.setToolTip("每个核验块的最大字符数，优先在换行处切分。")
        self.cfg_max_tokens = QSpinBox()
        self.cfg_max_tokens.setRange(1, 32768)
        self.cfg_max_tokens.setSingleStep(256)
        self.cfg_max_tokens.setToolTip("输出 token 上限；开启 thinking 时需要更大预算。")
        self.cfg_temperature = QDoubleSpinBox()
        self.cfg_temperature.setRange(0, 2)
        self.cfg_temperature.setSingleStep(0.1)
        self.cfg_thinking = QComboBox()
        self.cfg_thinking.addItem("默认", None)
        self.cfg_thinking.addItem("开启", True)
        self.cfg_thinking.addItem("关闭", False)
        self.cfg_min_confidence = QComboBox()
        for item in ("high", "medium", "low"):
            self.cfg_min_confidence.addItem(item, item)
        self.cfg_glossary = QLineEdit()
        self.cfg_glossary.setToolTip("术语表路径（相对 bookforge 目录），每行一个术语。")
        self.cfg_style = QPlainTextEdit()
        self.cfg_style.setMaximumHeight(80)
        self.cfg_style.setToolTip("给 LLM 的风格说明：保留作者用词、排除通假字等误报。")
        profile_layout.addRow("model", self.model_edit)
        profile_layout.addRow("base_url", self.base_url_edit)
        profile_layout.addRow("max_chars", self.cfg_max_chars)
        profile_layout.addRow("max_tokens", self.cfg_max_tokens)
        profile_layout.addRow("temperature", self.cfg_temperature)
        profile_layout.addRow("thinking", self.cfg_thinking)
        profile_layout.addRow("min_confidence", self.cfg_min_confidence)
        profile_layout.addRow("glossary", self.cfg_glossary)
        profile_layout.addRow("style", self.cfg_style)
        self.cfg_key_file = QLineEdit()
        self.cfg_key_file.setPlaceholderText("留空使用 keys/llm_api_key.txt")
        self.cfg_key_file.setToolTip("可选的 key 文件路径；相对路径基于 bookforge 目录。")
        profile_layout.addRow("key_file", self.cfg_key_file)
        layout.addWidget(profile_group)

        key_group = QGroupBox("API key")
        key_layout = QVBoxLayout(key_group)
        key_row = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("粘贴 API key（不会显示明文）")
        self.key_edit.setToolTip("密钥只写入 key 文件，不进入日志、报告或 git。")
        self.key_save_button = QPushButton("保存密钥")
        self.key_clear_button = QPushButton("清除密钥")
        key_row.addWidget(self.key_edit, 1)
        key_row.addWidget(self.key_save_button)
        key_row.addWidget(self.key_clear_button)
        key_layout.addLayout(key_row)
        self.key_hint = QLabel("保存后可直接使用“测试连接”。")
        self.key_hint.setWordWrap(True)
        key_layout.addWidget(self.key_hint)
        layout.addWidget(key_group)

        config_buttons = QHBoxLayout()
        self.config_save_button = QPushButton("保存配置")
        self.config_test_button = QPushButton("测试连接")
        config_buttons.addWidget(self.config_save_button)
        config_buttons.addWidget(self.config_test_button)
        config_buttons.addStretch(1)
        layout.addLayout(config_buttons)
        self.config_status = QLabel("")
        self.config_status.setWordWrap(True)
        layout.addWidget(self.config_status)

        install_group = QGroupBox("安装任务到游戏目录")
        install_layout = QGridLayout(install_group)
        self.install_job_edit = QLineEdit()
        self.install_job_edit.setToolTip("要安装到游戏的 job.json（通常是 reviewed/job.json）。")
        self.install_job_button = QPushButton("浏览")
        self.install_game_edit = QLineEdit()
        self.install_game_edit.setToolTip("包含 mods/ 与 config/ 的 Minecraft 目录。")
        self.install_game_button = QPushButton("浏览")
        self.install_button = QPushButton("安装到 autobook/jobs")
        self.install_button.setToolTip(
            "复制 job 到 游戏目录\\autobook\\jobs\\<书名>.json；游戏内 /autobook add 后使用。"
        )
        install_layout.addWidget(QLabel("job.json"), 0, 0)
        install_layout.addWidget(self.install_job_edit, 0, 1)
        install_layout.addWidget(self.install_job_button, 0, 2)
        install_layout.addWidget(QLabel("游戏目录"), 1, 0)
        install_layout.addWidget(self.install_game_edit, 1, 1)
        install_layout.addWidget(self.install_game_button, 1, 2)
        install_layout.addWidget(self.install_button, 2, 1, 1, 2)
        layout.addWidget(install_group)
        layout.addStretch(1)

        self.profile_combo.currentIndexChanged.connect(self._load_profile)
        self.key_save_button.clicked.connect(self._save_api_key)
        self.key_clear_button.clicked.connect(self._clear_api_key)
        self.config_save_button.clicked.connect(self._save_config)
        self.config_test_button.clicked.connect(self._test_connection)
        self.install_job_button.clicked.connect(self._browse_install_job)
        self.install_game_button.clicked.connect(self._browse_game_dir)
        self.install_button.clicked.connect(self._install_job)
        return widget

    def _build_help_tab(self) -> QWidget:
        widget = QWidget()
        self._help_tab = widget
        layout = QVBoxLayout(widget)

        buttons = QHBoxLayout()
        self.open_config_dir_button = QPushButton("打开配置目录")
        self.open_config_dir_button.setToolTip(
            "打开 keys 目录：llm_config.json、llm_api_key.txt、术语表所在位置。"
        )
        self.open_logs_dir_button = QPushButton("打开日志目录")
        self.open_logs_dir_button.setToolTip(
            "打开游戏目录下的 logs（AutoBook 运行日志 latest.log 所在位置）。"
        )
        self.open_game_dir_button = QPushButton("打开游戏目录")
        self.open_game_dir_button.setToolTip(
            "打开“配置”页中设置的游戏目录（包含 mods/ 与 config/）。"
        )
        buttons.addWidget(self.open_config_dir_button)
        buttons.addWidget(self.open_logs_dir_button)
        buttons.addWidget(self.open_game_dir_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.help_browser = QTextBrowser()
        self.help_browser.setOpenExternalLinks(False)
        layout.addWidget(self.help_browser, 1)
        self._refresh_help()

        self.open_config_dir_button.clicked.connect(self._open_config_dir)
        self.open_logs_dir_button.clicked.connect(self._open_logs_dir)
        self.open_game_dir_button.clicked.connect(self._open_game_dir)
        return widget

    def _on_tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self._help_tab:
            self._refresh_help()

    def _refresh_help(self) -> None:
        self.help_browser.setHtml(build_help_html(self.install_game_edit.text()))

    def _open_config_dir(self) -> None:
        target = BOOKFORGE_ROOT / "keys"
        target.mkdir(parents=True, exist_ok=True)
        self._open_dir(target)

    def _game_dir(self) -> Path | None:
        text = self.install_game_edit.text().strip()
        if not text:
            QMessageBox.information(
                self,
                "未设置游戏目录",
                "请先在“配置”页选择游戏目录（包含 mods/ 与 config/）。",
            )
            self.tabs.setCurrentWidget(self._config_tab)
            return None
        return Path(text)

    def _open_game_dir(self) -> None:
        game_dir = self._game_dir()
        if game_dir is not None:
            self._open_dir(game_dir)

    def _open_logs_dir(self) -> None:
        game_dir = self._game_dir()
        if game_dir is None:
            return
        logs = game_dir / "logs"
        self._open_dir(logs if logs.is_dir() else game_dir)

    def _open_dir(self, path: Path) -> None:
        if not path.is_dir():
            QMessageBox.warning(self, "目录不存在", f"找不到目录：\n{path}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ---------- helpers ----------

    def _row(self, edit: QLineEdit, button: QPushButton) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit, 1)
        layout.addWidget(button)
        return widget

    def _append_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)

    def _restore_paths(self) -> None:
        self.input_edit.setText(self._ui_settings.value("paths/input", ""))
        self.output_edit.setText(self._ui_settings.value("paths/output", ""))
        self.install_game_edit.setText(self._ui_settings.value("paths/game", ""))

    def _save_paths(self) -> None:
        self._ui_settings.setValue("paths/input", self.input_edit.text().strip())
        self._ui_settings.setValue("paths/output", self.output_edit.text().strip())
        self._ui_settings.setValue("paths/game", self.install_game_edit.text().strip())

    # ---------- prepare ----------

    def _browse_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择书稿",
            "",
            "书籍 (*.epub *.mobi *.azw3 *.azw *.kf8 *.prc *.fb2 *.docx *.txt *.md);;"
            "所有文件 (*)",
        )
        if not path:
            return
        self.input_edit.setText(path)
        source = Path(path)
        if not self.output_edit.text().strip():
            self.output_edit.setText(str(Path("work") / source.stem))
        if not self.title_edit.text().strip():
            self.title_edit.setText(source.stem)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            self.output_edit.text().strip(),
        )
        if path:
            self.output_edit.setText(path)

    def _prepare(self) -> None:
        if self._prepare_worker is not None and self._prepare_worker.isRunning():
            return

        input_text = self.input_edit.text().strip()
        if not input_text:
            QMessageBox.warning(self, "缺少输入", "请选择书稿文件。")
            return
        source = Path(input_text)
        if not source.is_file():
            QMessageBox.warning(self, "文件不存在", f"找不到文件：\n{source}")
            return

        output_text = self.output_edit.text().strip()
        if not output_text:
            output_text = str(Path("work") / source.stem)
            self.output_edit.setText(output_text)

        self.summary_label.setText("正在处理……")
        self.log_view.clear()
        self._append_log(f"输入: {source}")
        self._append_log(f"输出: {output_text}")
        self.prepare_button.setEnabled(False)
        self.progress.setRange(0, 0)

        worker = PrepareWorker(
            source,
            Path(output_text),
            self.title_edit.text().strip(),
            self.page_limit_spin.value(),
            self.max_chars_spin.value(),
            parent=self,
        )
        worker.log.connect(self._append_log)
        worker.succeeded.connect(self._on_prepare_success)
        worker.failed.connect(self._on_prepare_failure)
        worker.finished.connect(self._on_prepare_finished)
        self._prepare_worker = worker
        worker.start()

    def _on_prepare_success(self, outcome) -> None:
        summary = outcome.result.report["summary"]
        lines = [
            f"书名: {outcome.title}",
            f"章节: {summary['chapters']}",
            f"分段: {summary['segments']}",
            f"最大预估页数: {summary['max_estimated_pages']}",
            f"job: {outcome.result.job_path}",
            f"report: {outcome.result.report_path}",
        ]
        if outcome.imported is not None:
            imported = outcome.imported
            lines.insert(1, f"格式: {imported.format}")
            if imported.author:
                lines.insert(2, f"作者: {imported.author}")
            lines.insert(3, f"字符数: {len(imported.text)}")
            lines.append(f"导入警告: {len(imported.warnings)}")
            if outcome.import_report_path is not None:
                lines.append(f"import: {outcome.import_report_path}")

        self.summary_label.setText("\n".join(lines))
        self._append_log("完成。")
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.prepare_button.setEnabled(True)
        self.review_job_edit.setText(str(outcome.result.job_path))
        self.install_job_edit.setText(str(outcome.result.job_path))

    def _on_prepare_failure(self, message: str) -> None:
        self._append_log(f"ERROR: {message}")
        self.summary_label.setText(f"失败：{message}")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.prepare_button.setEnabled(True)
        QMessageBox.critical(self, "生成失败", message)

    def _on_prepare_finished(self) -> None:
        self._prepare_worker = None

    # ---------- review ----------

    def _browse_review_job(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 job.json",
            self.review_job_edit.text().strip(),
            "job (*.json);;所有文件 (*)",
        )
        if path:
            self.review_job_edit.setText(path)

    def _start_review(self) -> None:
        if self._review_worker is not None and self._review_worker.isRunning():
            return
        job_path_text = self.review_job_edit.text().strip()
        if not job_path_text:
            QMessageBox.warning(self, "缺少 job", "请选择 job.json。")
            return
        job_path = Path(job_path_text)
        if not job_path.is_file():
            QMessageBox.warning(self, "文件不存在", f"找不到 job：\n{job_path}")
            return
        try:
            job = validate_job_data(json.loads(job_path.read_text(encoding="utf-8")))
            profile = str(job.get("titleBase", "")).strip() or None
            settings = load_settings(profile=profile, strict_profile=False)
            glossary = _read_glossary(settings.glossary_file)
        except Exception as error:
            QMessageBox.critical(self, "配置错误", str(error))
            return

        mode = str(self.review_mode.currentData())
        out_path = job_path.parent / (
            "llm_patch.json" if mode == "patch" else "llm_report.json"
        )
        self._job = job
        self._job_path = job_path
        self._patch_report = None
        self._patch_path = None
        self.review_start_button.setEnabled(False)
        self.review_cancel_button.setEnabled(True)
        self.review_progress.setRange(0, 1)
        self.review_progress.setValue(0)
        self.review_summary.setText("正在核验……")
        self.review_model.set_issues([], mode)
        self._append_log(
            f"LLM {mode}: {job_path} profile={settings.profile_name or '-'}"
        )

        worker = ReviewWorker(
            job,
            job_path,
            settings,
            mode,
            self.review_sample.value(),
            out_path,
            glossary,
            parent=self,
        )
        worker.progress.connect(self._on_review_progress)
        worker.succeeded.connect(self._on_review_success)
        worker.failed.connect(self._on_review_failure)
        worker.finished.connect(self._on_review_finished)
        self._review_worker = worker
        worker.start()

    def _cancel_review(self) -> None:
        if self._review_worker is not None and self._review_worker.isRunning():
            self._review_worker.cancel()
            self.review_summary.setText("正在取消……")
            self.review_cancel_button.setEnabled(False)

    def _on_review_progress(self, done: int, total: int, message: str) -> None:
        self.review_progress.setRange(0, max(total, 1))
        self.review_progress.setValue(done)
        self.review_summary.setText(f"处理块 {done}/{total}: {message}")

    def _on_review_success(self, report: dict[str, Any], path: str) -> None:
        summary = report["summary"]
        usage = report["usage"]
        state = "已取消" if summary.get("cancelled") else "完成"
        lines = [
            f"{state}: {summary['chunks']}/{summary['plannedChunks']} 块",
            f"问题: {summary['issues']}，错误: {summary['errors']}，拦截: {summary['blocked']}",
            f"tokens: prompt={usage['promptTokens']}, completion={usage['completionTokens']}, "
            f"reasoning={usage['reasoningTokens']}, total={usage['totalTokens']}",
            f"报告: {path}",
        ]
        self.review_summary.setText("\n".join(lines))
        self._append_log("\n".join(lines))
        self.review_model.set_issues(report.get("issues", []), report.get("mode", "report"))
        self.review_progress.setValue(summary["chunks"])
        if report.get("mode") == "patch":
            self.patch_path_edit.setText(path)
            self._patch_report = report
            self._patch_path = Path(path)
            self.patch_model.set_issues(report.get("issues", []), "patch")
            self.patch_status.setText(
                f"已加载 {len(report.get('issues', []))} 条补丁，默认勾选 high 置信度。"
            )
            self.tabs.setCurrentWidget(self.patch_tab_widget())
        self.review_start_button.setEnabled(True)
        self.review_cancel_button.setEnabled(False)

    def _on_review_failure(self, message: str) -> None:
        self._append_log(f"ERROR: {message}")
        self.review_summary.setText(f"失败：{message}")
        self.review_start_button.setEnabled(True)
        self.review_cancel_button.setEnabled(False)
        QMessageBox.critical(self, "核验失败", message)

    def _on_review_finished(self) -> None:
        self._review_worker = None

    def patch_tab_widget(self) -> QWidget:
        return self.tabs.widget(2)

    # ---------- patch ----------

    def _browse_patch(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 patch.json",
            self.patch_path_edit.text().strip(),
            "patch (*.json);;所有文件 (*)",
        )
        if path:
            self.patch_path_edit.setText(path)

    def _load_patch(self) -> None:
        path_text = self.patch_path_edit.text().strip()
        if not path_text:
            QMessageBox.warning(self, "缺少补丁", "请选择 llm_patch.json。")
            return
        path = Path(path_text)
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("patch 文件根节点必须是对象")
            if report.get("version") != 1 or report.get("mode") != "patch":
                raise ValueError("不是 review --mode patch 的输出")
            issues = report.get("issues")
            if not isinstance(issues, list):
                raise ValueError("patch 文件缺少 issues 数组")
        except Exception as error:
            QMessageBox.critical(self, "加载失败", str(error))
            return

        self._patch_report = report
        self._patch_path = path
        self.patch_model.set_issues(issues, "patch")
        self.patch_status.setText(
            f"已加载 {len(issues)} 条补丁，默认勾选 high 置信度。"
        )
        self.rejected_view.clear()
        self.diff_view.clear()
        out_dir = path.parent / "reviewed"
        self.patch_out_edit.setText(str(out_dir))
        source_job = report.get("source", {}).get("job", "")
        if source_job and not self.review_job_edit.text().strip():
            self.review_job_edit.setText(source_job)
        if report.get("source", {}).get("titleBase"):
            self._append_log(
                f"补丁书名: {report['source'].get('titleBase')}"
            )

    def _browse_patch_out(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "选择 reviewed 输出目录",
            self.patch_out_edit.text().strip(),
        )
        if path:
            self.patch_out_edit.setText(path)

    def _apply_patch(self) -> None:
        if self._apply_worker is not None and self._apply_worker.isRunning():
            return
        if self._patch_report is None:
            QMessageBox.warning(self, "缺少补丁", "请先加载补丁文件。")
            return
        job_path_text = self.review_job_edit.text().strip()
        if not job_path_text:
            job_path_text = str(self._patch_report.get("source", {}).get("job", ""))
        if not job_path_text:
            QMessageBox.warning(self, "缺少 job", "请选择原始 job.json。")
            return
        job_path = Path(job_path_text)
        if not job_path.is_file():
            QMessageBox.warning(self, "文件不存在", f"找不到 job：\n{job_path}")
            return
        try:
            job = validate_job_data(json.loads(job_path.read_text(encoding="utf-8")))
        except Exception as error:
            QMessageBox.critical(self, "job 无效", str(error))
            return

        issues = self.patch_model.selected_issues()
        if not issues:
            QMessageBox.warning(self, "未选择补丁", "至少勾选一条补丁。")
            return
        policy = (
            self._patch_report.get("policy")
            if isinstance(self._patch_report.get("policy"), dict)
            else {}
        )
        min_confidence = str(policy.get("minConfidence", "high"))
        max_delta = policy.get("maxDelta") if isinstance(policy.get("maxDelta"), dict) else None
        out_text = self.patch_out_edit.text().strip()
        out_dir = Path(out_text) if out_text else job_path.parent / "reviewed"

        self.patch_apply_button.setEnabled(False)
        self.patch_status.setText(f"正在应用 {len(issues)} 条补丁……")
        worker = ApplyWorker(
            job,
            job_path,
            self._patch_path or Path(""),
            issues,
            out_dir,
            min_confidence,
            max_delta,
            parent=self,
        )
        worker.succeeded.connect(self._on_apply_success)
        worker.failed.connect(self._on_apply_failure)
        worker.finished.connect(self._on_apply_finished)
        self._apply_worker = worker
        worker.start()

    def _on_apply_success(self, result, diff_text: str, apply_path: str) -> None:
        lines = [
            f"applied: {result.applied_count}",
            f"rejected: {result.rejected_count}",
            f"segments changed: {result.segments_changed}",
            f"diff lines: {len(diff_text.splitlines())}",
            f"patch_apply: {apply_path}",
        ]
        self.patch_status.setText("\n".join(lines))
        self._append_log("\n".join(lines))
        self.diff_view.setPlainText(diff_text)
        if result.rejected:
            self.rejected_view.setPlainText(
                "\n".join(
                    f"segment={item.get('segment')} chunk={item.get('chunk')}: "
                    f"{item.get('reason')}"
                    for item in result.rejected
                )
            )
        else:
            self.rejected_view.setPlainText("无被拒绝补丁。")
        reviewed_job = Path(apply_path).parent / "job.json"
        self.install_job_edit.setText(str(reviewed_job))
        self.patch_apply_button.setEnabled(True)

    def _on_apply_failure(self, message: str) -> None:
        self.patch_status.setText(f"失败：{message}")
        self._append_log(f"ERROR: {message}")
        self.patch_apply_button.setEnabled(True)
        QMessageBox.critical(self, "应用失败", message)

    def _on_apply_finished(self) -> None:
        self._apply_worker = None

    # ---------- config ----------

    def _reload_profiles(self, select: str | None = None) -> None:
        config = read_config()
        names = profile_names(config)
        current = select
        if current is None and self.profile_combo.count() > 0:
            current = str(self.profile_combo.currentData() or "")
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for name in names:
            self.profile_combo.addItem(profile_label(name), name)
        index = max(0, self.profile_combo.findData(current or ""))
        self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)
        self._load_profile()

    def _load_profile(self) -> None:
        name = str(self.profile_combo.currentData() or "")
        config = read_config()
        values = profile_values(config, name)
        self.model_edit.setText(str(values.get("model", "")))
        self.base_url_edit.setText(str(values.get("base_url", "")))
        self.cfg_max_chars.setValue(int(values.get("max_chars", 4000) or 4000))
        self.cfg_max_tokens.setValue(int(values.get("max_tokens", 8192) or 8192))
        self.cfg_temperature.setValue(float(values.get("temperature", 0) or 0))
        thinking = values.get("thinking")
        index = 0 if thinking is None else 1 if thinking else 2
        self.cfg_thinking.setCurrentIndex(index)
        confidence = str(values.get("min_confidence", "high"))
        self.cfg_min_confidence.setCurrentIndex(
            max(0, self.cfg_min_confidence.findData(confidence))
        )
        self.cfg_glossary.setText(str(values.get("glossary", "") or ""))
        self.cfg_style.setPlainText(str(values.get("style", "") or ""))
        self.cfg_key_file.setText(str(values.get("key_file", "") or ""))
        self._refresh_key_status()

    def _profile_form_values(self) -> dict[str, Any]:
        return {
            "model": self.model_edit.text().strip(),
            "base_url": self.base_url_edit.text().strip(),
            "max_chars": self.cfg_max_chars.value(),
            "max_tokens": self.cfg_max_tokens.value(),
            "temperature": self.cfg_temperature.value(),
            "thinking": self.cfg_thinking.currentData(),
            "min_confidence": str(self.cfg_min_confidence.currentData()),
            "glossary": self.cfg_glossary.text().strip(),
            "style": self.cfg_style.toPlainText().strip(),
            "key_file": self.cfg_key_file.text().strip(),
        }

    def _save_config(self) -> None:
        name = str(self.profile_combo.currentData() or "")
        config = read_config()
        try:
            path = save_profile(config, name, self._profile_form_values())
        except Exception as error:
            QMessageBox.critical(self, "保存失败", str(error))
            return
        self.config_status.setText(f"已保存: {path}")
        self._append_log(f"配置已保存: {path}")
        self._refresh_key_status()

    def _refresh_key_status(self) -> None:
        name = str(self.profile_combo.currentData() or "")
        text = key_status(name)
        self.profile_key_label.setText(f"API key: {text}")
        self.key_hint.setText(f"当前 key：{text}")

    def _save_api_key(self) -> None:
        name = str(self.profile_combo.currentData() or "")
        value = self.key_edit.text()
        if not value.strip():
            QMessageBox.warning(self, "密钥为空", "请输入 API key 后再保存。")
            return
        try:
            path = save_api_key(value, name)
        except Exception as error:
            QMessageBox.critical(self, "保存密钥失败", str(error))
            return
        self.key_edit.clear()
        self._refresh_key_status()
        self.config_status.setText(f"密钥已保存: {path}")
        self._append_log(f"密钥已保存: {path}")

    def _clear_api_key(self) -> None:
        name = str(self.profile_combo.currentData() or "")
        answer = QMessageBox.question(
            self,
            "清除密钥",
            "确定删除当前 key 文件？已保存的密钥无法恢复。",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            path, removed = clear_api_key(name)
        except Exception as error:
            QMessageBox.critical(self, "清除密钥失败", str(error))
            return
        self._refresh_key_status()
        self.config_status.setText(
            f"密钥已删除: {path}" if removed else f"key 文件不存在: {path}"
        )
        self._append_log(self.config_status.text())

    def _test_connection(self) -> None:
        if (
            self._connection_worker is not None
            and self._connection_worker.isRunning()
        ):
            return
        name = str(self.profile_combo.currentData() or "")
        try:
            self._save_config()
            settings = load_settings(
                profile=name or None,
                strict_profile=bool(name),
            )
        except Exception as error:
            QMessageBox.critical(self, "配置错误", str(error))
            return
        self.config_status.setText("正在测试连接……")
        self.config_test_button.setEnabled(False)
        worker = ConnectionWorker(settings, parent=self)
        worker.succeeded.connect(self._on_connection_success)
        worker.failed.connect(self._on_connection_failure)
        worker.finished.connect(self._on_connection_finished)
        self._connection_worker = worker
        worker.start()

    def _on_connection_success(self, text: str) -> None:
        self.config_status.setText(f"连接成功: {text}")
        self._append_log(f"连接成功: {text}")
        self.config_test_button.setEnabled(True)

    def _on_connection_failure(self, message: str) -> None:
        self.config_status.setText(f"连接失败: {message}")
        self._append_log(f"连接失败: {message}")
        self.config_test_button.setEnabled(True)
        QMessageBox.critical(self, "连接失败", message)

    def _on_connection_finished(self) -> None:
        self._connection_worker = None

    def _browse_install_job(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择要安装的 job.json",
            self.install_job_edit.text().strip(),
            "job (*.json);;所有文件 (*)",
        )
        if path:
            self.install_job_edit.setText(path)

    def _browse_game_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "选择游戏目录（包含 mods/ 与 config/）",
            self.install_game_edit.text().strip(),
        )
        if path:
            self.install_game_edit.setText(path)

    def _install_job(self) -> None:
        job_text = self.install_job_edit.text().strip()
        game_text = self.install_game_edit.text().strip()
        if not job_text or not game_text:
            QMessageBox.warning(self, "缺少路径", "请选择 job.json 与游戏目录。")
            return
        try:
            destination = install_job(Path(job_text), Path(game_text))
        except Exception as error:
            QMessageBox.critical(self, "安装失败", str(error))
            return
        self.config_status.setText(f"已安装: {destination}")
        self._append_log(f"已安装: {destination}")
        QMessageBox.information(self, "安装完成", f"已复制到：\n{destination}")

    # ---------- lifecycle ----------

    def closeEvent(self, event) -> None:
        running = [
            worker
            for worker in (
                self._prepare_worker,
                self._review_worker,
                self._apply_worker,
                self._connection_worker,
            )
            if worker is not None and worker.isRunning()
        ]
        if running:
            QMessageBox.information(
                self,
                "正在处理",
                "仍有任务在运行，请等待完成或点击取消后再关闭。",
            )
            event.ignore()
            return
        self._save_paths()
        super().closeEvent(event)
