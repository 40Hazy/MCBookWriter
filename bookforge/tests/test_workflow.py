from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from bookforge.workflow import prepare_input

CONTAINER = """<?xml version="1.0" encoding="utf-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf"
              media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

OPF = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>流式测试书</dc:title>
    <dc:creator>作者甲</dc:creator>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="ch1"/>
  </spine>
</package>
"""

CH1 = """<html xmlns="http://www.w3.org/1999/xhtml"><body>
<h1>第一章</h1><p>正文一</p><p>正文二</p>
</body></html>"""


def make_epub(tmp_path: Path) -> Path:
    path = tmp_path / "book.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("OEBPS/content.opf", OPF)
        archive.writestr("OEBPS/ch1.xhtml", CH1)
    return path


def test_prepare_text_uses_explicit_title(tmp_path: Path) -> None:
    source = tmp_path / "novel.txt"
    source.write_text("第一章\n正文一\n\n正文二\n", encoding="utf-8")

    outcome = prepare_input(source, tmp_path / "out", title="测试书名")

    assert outcome.imported is None
    assert outcome.imported_text_path is None
    assert outcome.import_report_path is None
    assert outcome.title == "测试书名"
    assert outcome.result.job_path.is_file()
    assert outcome.result.job["titleBase"] == "测试书名"


def test_prepare_epub_writes_import_files(tmp_path: Path) -> None:
    source = make_epub(tmp_path)

    outcome = prepare_input(source, tmp_path / "out")

    assert outcome.imported is not None
    assert outcome.title == "流式测试书"
    assert outcome.imported_text_path is not None
    assert outcome.imported_text_path.is_file()
    assert outcome.import_report_path is not None

    data = json.loads(outcome.import_report_path.read_text(encoding="utf-8"))
    assert data["format"] == "epub"
    assert data["author"] == "作者甲"
    assert data["textChars"] == len(outcome.imported.text)
    assert data["textPath"] == "00_imported.txt"
    assert len(data["sourceHash"]) == 64
    assert outcome.result.job["titleBase"] == "流式测试书"


def test_prepare_rejects_long_title(tmp_path: Path) -> None:
    source = tmp_path / "book.txt"
    source.write_text("第一章\n正文\n", encoding="utf-8")

    with pytest.raises(ValueError, match="24"):
        prepare_input(source, tmp_path / "out", title="超" * 40)
