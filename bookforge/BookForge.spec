# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

SPEC_DIR = Path(SPECPATH)
ROOT = SPEC_DIR.parent
PACKAGE = SPEC_DIR / "bookforge"
KEYS = SPEC_DIR / "keys"

datas = [
    (str(ROOT / "docs" / "job.schema.json"), "docs"),
    (str(KEYS / "llm_config.json"), "keys"),
]
for glossary in KEYS.glob("glossary*.txt"):
    datas.append((str(glossary), "keys"))

a = Analysis(
    [str(PACKAGE / "gui" / "app.py")],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BookForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="BookForge",
)
