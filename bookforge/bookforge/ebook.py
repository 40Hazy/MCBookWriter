from __future__ import annotations

import os
import posixpath
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET


class EbookError(RuntimeError):
    pass


NATIVE_SUFFIXES = {".epub", ".fb2", ".docx"}
CALIBRE_SUFFIXES = {".azw3", ".mobi", ".azw", ".kf8", ".prc"}
SUPPORTED_SUFFIXES = NATIVE_SUFFIXES | CALIBRE_SUFFIXES


@dataclass(frozen=True)
class ImportedBook:
    format: str
    text: str
    title: str
    author: str
    warnings: list[str] = field(default_factory=list)


def is_ebook(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_SUFFIXES


def extract_ebook(path: str | Path, *, calibre: str | None = None) -> ImportedBook:
    source = Path(path)
    suffix = source.suffix.lower()

    if suffix == ".epub":
        return _extract_epub(source)
    if suffix == ".fb2":
        return _extract_fb2(source)
    if suffix == ".docx":
        return _extract_docx(source)
    if suffix in CALIBRE_SUFFIXES:
        tool = find_calibre(calibre)
        if tool:
            return _convert_with_calibre(source, tool)
        return _extract_with_mobi(source)

    raise EbookError(
        f"不支持的电子书格式: {suffix}。支持 "
        + "、".join(sorted(SUPPORTED_SUFFIXES))
    )


def find_calibre(explicit: str | None = None) -> str | None:
    candidates: list[str | None] = [
        explicit,
        os.environ.get("BOOKFORGE_CALIBRE"),
        shutil.which("ebook-convert"),
    ]
    if os.name == "nt":
        candidates.extend(
            [
                r"C:\Program Files\Calibre2\ebook-convert.exe",
                r"C:\Program Files (x86)\Calibre2\ebook-convert.exe",
            ]
        )
    else:
        candidates.append("/Applications/calibre.app/Contents/MacOS/ebook-convert")

    for candidate in candidates:
        if not candidate:
            continue
        if Path(candidate).is_file():
            return str(candidate)
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _convert_with_calibre(source: Path, tool: str) -> ImportedBook:
    with tempfile.TemporaryDirectory(prefix="bookforge-ebook-") as temp_dir:
        converted = Path(temp_dir) / "converted.epub"
        command = [tool, str(source), str(converted), "--no-images"]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        except OSError as error:
            raise EbookError(f"无法启动 Calibre: {error}") from error
        except subprocess.TimeoutExpired as error:
            raise EbookError("Calibre 转换超时") from error

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[-500:]
            hint = ""
            lower = detail.lower()
            if "drm" in lower or "encrypt" in lower:
                hint = "（文件可能受 DRM 保护，本项目不处理 DRM）"
            raise EbookError(f"Calibre 转换失败{hint}: {detail}")
        if not converted.is_file():
            raise EbookError("Calibre 未生成 EPUB 文件")

        imported = _extract_epub(converted)
        warnings = [
            f"已通过 Calibre 转换为 EPUB: {source.suffix.lower()}",
            *imported.warnings,
        ]
        return ImportedBook(
            format=source.suffix.lstrip("."),
            text=imported.text,
            title=imported.title,
            author=imported.author,
            warnings=warnings,
        )


def _extract_with_mobi(source: Path) -> ImportedBook:
    try:
        import mobi
    except ImportError as error:
        raise EbookError(
            f"{source.suffix} 需要 Calibre 的 ebook-convert，"
            "或安装 Python 解析库：pip install mobi；仅支持无 DRM 的文件。"
        ) from error

    tempdir: str | None = None
    try:
        tempdir, output = mobi.extract(str(source))
        output_path = Path(output)
        if output_path.suffix.lower() == ".epub":
            imported = _extract_epub(output_path)
        elif output_path.suffix.lower() in {".html", ".htm"}:
            html = output_path.read_text(encoding="utf-8", errors="replace")
            text = _html_to_text(html)
            if not text.strip():
                raise EbookError("mobi 提取结果为空")
            imported = ImportedBook(
                format="html",
                text=text,
                title="",
                author="",
                warnings=[],
            )
        else:
            raise EbookError(f"mobi 提取返回了不支持的格式: {output_path.suffix}")
    except EbookError:
        raise
    except Exception as error:
        raise EbookError(
            f"MOBI/AZW3 解析失败（可能受 DRM 保护）: {error}"
        ) from error
    finally:
        if tempdir:
            shutil.rmtree(tempdir, ignore_errors=True)

    return ImportedBook(
        format=source.suffix.lstrip("."),
        text=imported.text,
        title=imported.title,
        author=imported.author,
        warnings=[
            f"通过 Python mobi 库提取: {source.suffix.lower()}",
            *imported.warnings,
        ],
    )


def _extract_epub(path: Path) -> ImportedBook:
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.flag_bits & 0x1:
                    raise EbookError(
                        "EPUB 包含加密条目，可能受 DRM 保护；请使用无 DRM 的副本。"
                    )

            container_xml = ET.fromstring(
                _read_zip_text(archive, "META-INF/container.xml", warnings)
            )
            opf_path = next(
                (
                    element.attrib.get("full-path")
                    for element in container_xml.iter()
                    if _local_name(element.tag) == "rootfile"
                ),
                None,
            )
            if not opf_path:
                raise EbookError("EPUB 缺少 OPF 入口（META-INF/container.xml）")

            opf = ET.fromstring(_read_zip_text(archive, opf_path, warnings))
            base_dir = posixpath.dirname(opf_path)

            title = ""
            author = ""
            for element in opf.iter():
                tag = _local_name(element.tag)
                if tag == "title" and not title:
                    title = "".join(element.itertext()).strip()
                elif tag == "creator" and not author:
                    author = "".join(element.itertext()).strip()

            manifest: dict[str, dict[str, str]] = {}
            for element in opf.iter():
                if _local_name(element.tag) != "item":
                    continue
                item_id = element.attrib.get("id")
                href = element.attrib.get("href")
                if item_id and href:
                    manifest[item_id] = {
                        "href": href,
                        "media-type": element.attrib.get("media-type", ""),
                        "properties": element.attrib.get("properties", ""),
                    }

            spine = [
                element.attrib.get("idref")
                for element in opf.iter()
                if _local_name(element.tag) == "itemref"
            ]

            parts: list[str] = []
            for idref in spine:
                if not idref:
                    continue
                item = manifest.get(idref)
                if not item:
                    warnings.append(f"spine 引用了不存在的条目: {idref}")
                    continue
                properties = item["properties"].split()
                if "nav" in properties:
                    continue
                href = item["href"].split("#", 1)[0]
                media_type = item["media-type"].lower()
                if not (
                    media_type in {
                        "application/xhtml+xml",
                        "text/html",
                        "application/xml",
                        "text/x-oeb1-document",
                    }
                    or href.lower().endswith((".xhtml", ".html", ".htm"))
                ):
                    continue

                member = posixpath.normpath(posixpath.join(base_dir, unquote(href)))
                try:
                    raw = archive.read(member)
                except KeyError:
                    warnings.append(f"缺少 EPUB 条目: {member}")
                    continue
                html = _decode_bytes(raw, warnings, member)
                try:
                    text = _html_to_text(html)
                except Exception as error:
                    warnings.append(f"{member}: HTML 解析失败 ({error})")
                    continue
                if _looks_like_toc(html, text, member):
                    warnings.append(f"跳过疑似目录页: {member}")
                    continue
                if text.strip():
                    parts.append(text)

        if not parts:
            raise EbookError("EPUB 未提取到正文")
        return ImportedBook(
            format="epub",
            text=_normalize_text("\n\n".join(parts)),
            title=title,
            author=author,
            warnings=warnings,
        )
    except zipfile.BadZipFile as error:
        raise EbookError(f"EPUB 文件损坏或不是 ZIP: {error}") from error
    except ET.ParseError as error:
        raise EbookError(f"EPUB XML 解析失败: {error}") from error


def _extract_fb2(path: Path) -> ImportedBook:
    warnings: list[str] = []
    try:
        tree = ET.parse(path)
    except ET.ParseError as error:
        raise EbookError(f"FB2 XML 解析失败: {error}") from error
    root = tree.getroot()

    title = ""
    author = ""
    for element in root.iter():
        tag = _local_name(element.tag)
        if tag == "book-title" and not title:
            title = "".join(element.itertext()).strip()
        elif tag == "author" and not author:
            author = " ".join(
                part.strip()
                for part in (
                    _find_text(element, "first-name"),
                    _find_text(element, "last-name"),
                    _find_text(element, "nickname"),
                )
                if part.strip()
            )

    lines: list[str] = []

    def walk(element: ET.Element) -> None:
        tag = _local_name(element.tag)
        if tag in {"binary"}:
            return
        if tag == "p":
            value = "".join(element.itertext()).strip()
            if value:
                lines.append(value)
            return
        if tag == "subtitle":
            value = "".join(element.itertext()).strip()
            if value:
                lines.append(value)
            return
        if tag == "empty-line":
            lines.append("")
            return
        for child in element:
            walk(child)

    walk(root)
    text = _normalize_text("\n".join(lines))
    if not text:
        raise EbookError("FB2 未提取到正文")
    return ImportedBook(
        format="fb2",
        text=text,
        title=title,
        author=author,
        warnings=warnings,
    )


def _extract_docx(path: Path) -> ImportedBook:
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            if "word/document.xml" not in archive.namelist():
                raise EbookError("DOCX 缺少 word/document.xml")
            document = ET.fromstring(archive.read("word/document.xml"))
            title = ""
            author = ""
            if "docProps/core.xml" in archive.namelist():
                core = ET.fromstring(archive.read("docProps/core.xml"))
                for element in core.iter():
                    tag = _local_name(element.tag)
                    if tag == "title" and not title:
                        title = (element.text or "").strip()
                    elif tag == "creator" and not author:
                        author = (element.text or "").strip()
    except zipfile.BadZipFile as error:
        raise EbookError(f"DOCX 文件损坏或不是 ZIP: {error}") from error
    except ET.ParseError as error:
        raise EbookError(f"DOCX XML 解析失败: {error}") from error

    lines: list[str] = []
    for paragraph in document.iter():
        if _local_name(paragraph.tag) != "p":
            continue
        parts: list[str] = []
        for node in paragraph.iter():
            tag = _local_name(node.tag)
            if tag == "t":
                parts.append(node.text or "")
            elif tag in {"br", "cr"}:
                parts.append("\n")
        value = "".join(parts).rstrip()
        if value.strip():
            lines.extend(value.split("\n"))

    text = _normalize_text("\n".join(lines))
    if not text:
        raise EbookError("DOCX 未提取到正文")
    return ImportedBook(
        format="docx",
        text=text,
        title=title,
        author=author,
        warnings=warnings,
    )


class _HtmlTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "p",
        "div",
        "section",
        "article",
        "blockquote",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "tr",
        "td",
        "th",
        "br",
        "hr",
        "pre",
        "figure",
        "figcaption",
        "body",
    }
    SKIP_TAGS = {"script", "style", "head", "nav"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        self._start(tag)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self._start(tag)

    def _start(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return _normalize_text("".join(self.parts))


def _html_to_text(html: str) -> str:
    extractor = _HtmlTextExtractor()
    extractor.feed(html)
    extractor.close()
    return extractor.text()


_TOC_TITLES = {
    "目录",
    "目次",
    "contents",
    "tableofcontents",
    "toc",
}
_CHAPTER_HEADING = re.compile(r"^第[一二三四五六七八九十百千万0-9]+[回章节卷]")


def _looks_like_toc(html: str, text: str, name: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False

    anchors = html.lower().count("<a ")
    first = lines[0].replace(" ", "").lower()
    if first in _TOC_TITLES and anchors >= 3:
        return True

    stem = Path(name).stem.lower()
    if (
        any(token in stem for token in ("toc", "nav", "contents", "mulu", "directory"))
        and anchors >= 5
        and len(text) < 6000
    ):
        return True

    if anchors < 15 or len(text) > 6000:
        return False
    chapter_lines = sum(1 for line in lines if _CHAPTER_HEADING.match(line))
    short_ratio = sum(1 for line in lines if len(line) <= 40) / len(lines)
    return chapter_lines >= 5 and short_ratio >= 0.6


def _read_zip_text(archive: zipfile.ZipFile, name: str, warnings: list[str]) -> str:
    try:
        raw = archive.read(name)
    except KeyError as error:
        raise EbookError(f"EPUB 缺少条目: {name}") from error
    return _decode_bytes(raw, warnings, name)


def _decode_bytes(raw: bytes, warnings: list[str], name: str) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    warnings.append(f"{name}: 编码无法确定，使用 latin-1 兜底")
    return raw.decode("latin-1")


def _normalize_text(text: str) -> str:
    text = (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\xa0", " ")
        .replace("\ufeff", "")
    )
    lines = [line.rstrip() for line in text.split("\n")]
    output: list[str] = []
    blank = False
    for line in lines:
        if line.strip():
            output.append(line)
            blank = False
        elif not blank:
            output.append("")
            blank = True
    while output and not output[0].strip():
        output.pop(0)
    while output and not output[-1].strip():
        output.pop()
    return "\n".join(output)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_text(element: ET.Element, name: str) -> str:
    for child in element:
        if _local_name(child.tag) == name:
            return (child.text or "").strip()
    return ""
