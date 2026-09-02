# PyInstaller spec for the Tauri sidecar (#152) -- freezes web/main.py +
# uvicorn into a single executable the Tauri shell spawns as
# `binaries/scilene-server-<target-triple>`. Run from the project root:
#   pyinstaller scilene-server.spec --clean
#
# Requires the desktop dependency set (requirements.txt +
# requirements-desktop.txt) installed in whatever environment runs this
# -- see docs/DESKTOP_BUILD.md.

import os
import sys

block_cipher = None

# ctranslate2 ships its actual native library outside the normal
# Python import graph -- PyInstaller's static analysis can't see it,
# and there's no bundled hook for ctranslate2 in
# pyinstaller-hooks-contrib (verified on Linux: hooks exist for torch,
# onnxruntime, langdetect, but not ctranslate2, tokenizers,
# argostranslate, or stanza). Without this, the frozen binary starts,
# then crashes the first time Argos actually runs inference -- not on
# startup, so easy to miss if untested.
#
# Linux: verified directly (#152) -- a sibling `ctranslate2.libs/`
# directory (auditwheel-repaired wheel layout), loaded via RPATH.
# Windows/macOS branches below are UNVERIFIED -- this environment has
# no Windows/macOS machine to actually build and check the frozen
# binary against (same limitation already documented in
# docs/DESKTOP_BUILD.md's Platform notes). They assume ctranslate2's
# DLLs/dylibs sit directly in its own package directory on those
# platforms rather than a similar delvewheel/delocate-repaired sibling
# `.libs`-style folder -- plausible (both PyPI wheel formats commonly
# bundle this way), not confirmed. Verify against a real Windows/macOS
# build before relying on this; if the frozen binary crashes the same
# way the Linux one did before this fix, check for a sibling
# `ctranslate2.libs*` folder next to the package first.
def get_native_binaries():
    binaries = []
    if sys.platform == "linux":
        import ctranslate2
        ct2_dir = os.path.join(os.path.dirname(ctranslate2.__file__), "..")
        ct2_libs = os.path.join(ct2_dir, "ctranslate2.libs")
        if os.path.isdir(ct2_libs):
            for f in os.listdir(ct2_libs):
                if f.endswith(".so") or ".so." in f:
                    binaries.append((os.path.join(ct2_libs, f), "ctranslate2.libs"))
    elif sys.platform == "win32":
        # ctranslate2 ships DLLs in its own directory on Windows
        import ctranslate2
        ct2_dir = os.path.dirname(ctranslate2.__file__)
        for f in os.listdir(ct2_dir):
            if f.endswith(".dll"):
                binaries.append((os.path.join(ct2_dir, f), "."))
    elif sys.platform == "darwin":
        # macOS: .dylib files in ctranslate2 package dir
        import ctranslate2
        ct2_dir = os.path.dirname(ctranslate2.__file__)
        for f in os.listdir(ct2_dir):
            if f.endswith(".dylib"):
                binaries.append((os.path.join(ct2_dir, f), "."))
    return binaries


a = Analysis(
    ["web/main.py"],
    pathex=["."],
    binaries=get_native_binaries(),
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
