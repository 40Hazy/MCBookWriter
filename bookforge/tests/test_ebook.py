from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from bookforge.ebook import EbookError, extract_ebook
from bookforge.manifest import validate_job
from bookforge.pipeline import prepare_document

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
    <dc:title>测试书</dc:title>
    <dc:creator>作者甲</dc:creator>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="toc" href="toc.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="ch1"/>
    <itemref idref="ch2"/>
    <itemref idref="nav"/>
    <itemref idref="toc"/>
  </spine>
</package>
"""

CH1 = """<html xmlns="http://www.w3.org/1999/xhtml"><body>
<h1>第一章</h1><p>第一段</p><p>第二段</p>
</body></html>"""

CH2 = """<html xmlns="http://www.w3.org/1999/xhtml"><body>
<h1>第二章</h1><p>第三段</p>
</body></html>"""

NAV = """<html xmlns="http://www.w3.org/1999/xhtml"><body>
<nav><p>目录</p></nav>
</body></html>"""

TOC = """<html xmlns="http://www.w3.org/1999/xhtml"><body>
<h1>目录</h1>
<p><a href="ch1.xhtml">第一章</a></p>
<p><a href="ch2.xhtml">第二章</a></p>
<p><a href="ch1.xhtml">前言</a></p>
</body></html>"""


def make_epub(tmp_path: Path) -> Path:
    path = tmp_path / "book.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("OEBPS/content.opf", OPF)
        archive.writestr("OEBPS/ch1.xhtml", CH1)
        archive.writestr("OEBPS/ch2.xhtml", CH2)
        archive.writestr("OEBPS/nav.xhtml", NAV)
        archive.writestr("OEBPS/toc.xhtml", TOC)
    return path


def test_extract_epub_reads_spine_and_skips_nav(tmp_path: Path) -> None:
    imported = extract_ebook(make_epub(tmp_path))

    assert imported.format == "epub"
    assert imported.title == "测试书"
    assert imported.author == "作者甲"
    assert "第一章" in imported.text
    assert "第三段" in imported.text
    assert "目录" not in imported.text
    assert any("跳过疑似目录页" in warning for warning in imported.warnings)


def test_extract_fb2(tmp_path: Path) -> None:
    path = tmp_path / "book.fb2"
    path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <book-title>FB2书名</book-title>
  <author><first-name>张</first-name><last-name>三</last-name></author>
  <body>
    <section>
      <title><p>第一章</p></title>
      <p>正文一</p>
      <empty-line/>
      <p>正文二</p>
    </section>
  </body>
</FictionBook>""",
        encoding="utf-8",
    )

    imported = extract_ebook(path)

    assert imported.format == "fb2"
    assert imported.title == "FB2书名"
    assert imported.author == "张 三"
    assert "第一章" in imported.text
    assert "正文二" in imported.text


def test_extract_docx(tmp_path: Path) -> None:
    path = tmp_path / "book.docx"
    document = """<?xml version="1.0" encoding="utf-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>第一章</w:t></w:r></w:p>
    <w:p><w:r><w:t>正文一</w:t></w:r></w:p>
    <w:p><w:r><w:t>正文二</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    core = """<?xml version="1.0" encoding="utf-8"?>
<cp:coreProperties
    xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
    xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>DOCX书名</dc:title>
  <dc:creator>作者乙</dc:creator>
</cp:coreProperties>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("docProps/core.xml", core)

    imported = extract_ebook(path)

    assert imported.format == "docx"
    assert imported.title == "DOCX书名"
    assert imported.author == "作者乙"
    assert "第一章" in imported.text
    assert "正文二" in imported.text


def test_mobi_without_calibre_raises_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "book.mobi"
    path.write_bytes(b"not a real mobi")
    monkeypatch.setattr("bookforge.ebook.find_calibre", lambda explicit=None: None)

    with pytest.raises(EbookError, match="MOBI|Calibre|mobi"):
        extract_ebook(path)


def test_epub_can_feed_prepare_pipeline(tmp_path: Path) -> None:
    imported = extract_ebook(make_epub(tmp_path))
    text_path = tmp_path / "imported.txt"
    text_path.write_text(imported.text + "\n", encoding="utf-8")

    result = prepare_document(
        text_path,
        tmp_path / "out",
        title=imported.title,
    )

    job = validate_job(result.job_path)
    assert job["titleBase"] == "测试书"
    assert job["segments"]
    assert "第一章" in job["segments"][0]["text"]
