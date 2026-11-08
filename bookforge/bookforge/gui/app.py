from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "缺少 PySide6。请先安装 GUI 依赖：pip install -e \".[gui]\"",
            file=sys.stderr,
        )
        return 1

    try:
        from .main_window import MainWindow
    except ImportError:
        # PyInstaller 把本文件当作 __main__ 运行时没有包上下文，改用绝对导入。
        from bookforge.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("BookForge")
    app.setApplicationDisplayName("BookForge")
    window = MainWindow()
    window.resize(1080, 820)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
