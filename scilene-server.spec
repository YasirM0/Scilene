# PyInstaller spec for the Tauri sidecar (#152) -- freezes web/main.py +
# uvicorn into a single executable the Tauri shell spawns as
# `binaries/scilene-server-<target-triple>`. Run from the project root:
#   pyinstaller scilene-server.spec --clean
#
# Requires the desktop dependency set (requirements.txt +
# requirements-desktop.txt) installed in whatever environment runs this
# -- see docs/DESKTOP_BUILD.md.

import os

import ctranslate2

block_cipher = None

# ctranslate2 ships its actual native library in a sibling
# `ctranslate2.libs/` directory (auditwheel-repaired wheel layout),
# loaded via RPATH rather than a normal Python import -- PyInstaller's
# static import-graph analysis can't see it, and there's no bundled
# hook for ctranslate2 in pyinstaller-hooks-contrib (verified: hooks
# exist for torch, onnxruntime, langdetect, but not ctranslate2,
# tokenizers, argostranslate, or stanza). Without this, the frozen
# binary starts, then crashes the first time Argos actually runs
# inference: "cannot open shared object file: No such file or
# directory" -- not on startup, so easy to miss if untested.
_ct2_dir = os.path.dirname(ctranslate2.__file__)
_ct2_libs_dir = os.path.join(os.path.dirname(_ct2_dir), "ctranslate2.libs")
_ct2_binaries = []
if os.path.isdir(_ct2_libs_dir):
    for fname in os.listdir(_ct2_libs_dir):
        if ".so" in fname:
            _ct2_binaries.append(
                (os.path.join(_ct2_libs_dir, fname), "ctranslate2.libs")
            )

a = Analysis(
    ["web/main.py"],
    pathex=["."],
    binaries=_ct2_binaries,
    datas=[
        ("data/journal_intelligence.db", "data"),
        ("models", "models"),
        ("web/templates", "web/templates"),
        ("web/static", "web/static"),
        ("data/indonesian_academic_dict.json", "data"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "onnxruntime",
        "tokenizers",
        "langdetect",
        "argostranslate",
        "argostranslate.translate",
        "argostranslate.package",
        "stanza",
        "ctranslate2",
        "services.semantic_search",
        "services.repository",
        "services.query_translator",
        "web.routers.search",
        "web.routers.research_idea",
    ],
    hookspath=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# a.binaries/a.zipfiles/a.datas passed directly into EXE() (rather than
# a separate COLLECT() step) is what makes this a one-file build --
# there is no `onefile=` kwarg on EXE() itself.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="scilene-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # keep True -- sidecar runs headless
)
