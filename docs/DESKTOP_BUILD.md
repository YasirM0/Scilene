# Desktop Build

How to build the Tauri desktop shell (#152) and its FastAPI sidecar
locally. Nothing here runs in CI or on a hosted deploy — the web/Heroku
build never touches any of this (see `docs/DEPLOYMENT.md`).

---

## Prerequisites

- **Node.js + npm** — drives the Tauri CLI (`npm install`, `npm run tauri ...`).
- **Rust + Cargo** — compiles `src-tauri/`.
- **Linux only:** `webkit2gtk4.1-devel`, `javascriptcoregtk4.1-devel`,
  `libsoup3-devel`, plus a C toolchain (`gcc`, `gcc-c++`, `make`) and
  `pkgconf-pkg-config`. On Fedora:
  ```bash
  sudo dnf install webkit2gtk4.1-devel javascriptcoregtk4.1-devel \
    libsoup3-devel gcc gcc-c++ make pkgconf-pkg-config openssl-devel \
    libappindicator-gtk3-devel librsvg2-devel
  ```
- **Python** matching `requirements.txt` + `requirements-desktop.txt`,
  plus PyInstaller, in a dedicated venv — see below. Don't reuse your
  everyday dev venv for this: PyInstaller freezes *everything* it can
  reach on `sys.path`, so an unrelated package sitting in the same
  environment can silently end up inside the frozen binary.

```bash
python3 -m venv .desktop-build-venv
source .desktop-build-venv/bin/activate
pip install -r requirements.txt -r requirements-desktop.txt pyinstaller
```

**Use the CPU-only torch wheel, not the default one.** `argostranslate`
pulls in `stanza`, which pulls in `torch` — and a plain `pip install`
grabs the full CUDA build plus a dozen `nvidia-*` packages (multiple
extra GB) that this app never uses (`ctranslate2` runs inference on
CPU regardless of what torch is installed). After the install above:

```bash
pip uninstall -y torch $(pip list --format=freeze | grep -o '^nvidia-[a-z0-9-]*' )
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

This alone is the difference between an unusable multi-GB build and a
merely-large one — CPU-only `torch` is still ~770MB on disk (it's the
single biggest thing in the frozen binary by far; ONNX retrieval model
+ SQLite DB together are under 150MB).

**Cache the MiniSBD "ar" sentence-boundary model too, not just the
Argos ar→en language package.** `services/query_translator.py` sets
`ARGOS_CHUNK_TYPE=MINISBD` before argostranslate is ever imported (#154)
— left at its default, argostranslate's sentence-splitting step for
Arabic uses `stanza.Pipeline()`, which unconditionally checks
`raw.githubusercontent.com` for a resources manifest on every call,
even when the translation model itself is already fully cached. A
genuinely offline machine hit exactly that: Arabic silently fell back
to the same `ArabicNotSupportedOnline` message that's supposed to be a
web-only limitation, found by `tests/test_offline.py`'s hard
network-block fixture. MiniSBD is argostranslate's own self-contained
ONNX sentence splitter and has no such check — but it downloads its
model file on first use exactly like the Argos package did, so that
also needs a one-time, online, pre-build step:

```bash
source .desktop-build-venv/bin/activate
ARGOS_CHUNK_TYPE=MINISBD python3 -c "import argostranslate.sbd as sbd; sbd.minisbd_models.get_model_file('ar')"
```

This downloads to `argostranslate.settings.data_dir / "minisbd" / "ar.onnx"`
(inside whatever `XDG_DATA_HOME`/platform data dir Argos resolves to in
the build environment) — bundle that file the same way the Argos
`ar_en` package itself gets bundled, or the frozen binary will hit the
same silent fallback on a genuinely offline install.

---

## Step by step

### 1. Build the sidecar binary

```bash
source .desktop-build-venv/bin/activate
pyinstaller scilene-server.spec --clean
```

This produces `dist/scilene-server` (~670MB — expected; see the torch
note above). `scilene-server.spec` is committed; the binary is not
(`.gitignore` excludes `src-tauri/binaries/` and `dist/`).

### 2. Copy it into place

The binary must go in **`src-tauri/binaries/`**, not the project
root — `externalBin` paths in `src-tauri/tauri.conf.json` resolve
relative to `src-tauri/`, and Tauri's build script fails immediately
(`resource path ... doesn't exist`) if it's anywhere else.

```bash
mkdir -p src-tauri/binaries
cp dist/scilene-server src-tauri/binaries/scilene-server-x86_64-unknown-linux-gnu
chmod +x src-tauri/binaries/scilene-server-x86_64-unknown-linux-gnu
```

The suffix is Rust's target triple, not a free-form name — Tauri
looks up the sidecar by appending the exact triple of whatever
platform you're building for (see Platform notes below).

Sanity-check it directly before going near Tauri:
```bash
./src-tauri/binaries/scilene-server-x86_64-unknown-linux-gnu --port 8765 &
curl http://127.0.0.1:8765/health
```

### 3. Build the Tauri shell

```bash
npm install          # once, or after package.json changes
cd src-tauri && cargo build
```

`cargo build` fails with the exact `resource path ... doesn't exist`
error from step 2 if the binary is missing or misplaced — that error
means go back to step 2, not a Rust problem.

### 4. Run it

```bash
npm run tauri dev
```

---

## Updating the binary after a `web/main.py` (or any `services/`/`web/`) change

The frozen binary is a snapshot — editing app code does nothing until
you refreeze it. Repeat steps 1–2 above (`pyinstaller ... --clean` is
safest after any dependency change; a plain `pyinstaller scilene-server.spec`
without `--clean` is faster for a source-only change and was
sufficient in testing, but re-verify with `--clean` before shipping).
Then re-run `cargo build`/`npm run tauri dev` to pick up the new
binary — Tauri doesn't rebuild the sidecar itself, only bundles
whatever's sitting in `src-tauri/binaries/` at cargo-build time.

If you add a new dependency to `requirements-desktop.txt` (or an
existing one starts vendoring a native library the way `ctranslate2`
does — see the comment at the top of `scilene-server.spec`), check
whether it needs an explicit `binaries=[]` entry in the spec: no
`pyinstaller-hooks-contrib` hook exists today for `ctranslate2`,
`tokenizers`, `argostranslate`, or `stanza` (only `torch`,
`onnxruntime`, and `langdetect` have one), so anything those add that
lives outside its own package directory (an `auditwheel`-style
`<pkg>.libs/` sibling folder, specifically) needs to be added by hand
the same way `ctranslate2.libs/` was.

---

## Platform notes

Only Linux (`x86_64-unknown-linux-gnu`) has actually been built and
tested — this whole document was verified end to end on that target,
including a real search request and a real Arabic query against the
frozen binary. macOS and Windows are untested and will need their own
target-triple-suffixed binaries:

- **macOS:** `scilene-server-x86_64-apple-darwin` (Intel) and/or
  `scilene-server-aarch64-apple-darwin` (Apple Silicon) — PyInstaller
  must run natively on each architecture you ship; it does not
  cross-compile.
- **Windows:** `scilene-server-x86_64-pc-windows-msvc.exe` — note the
  `.exe` suffix, which Linux/macOS builds don't have.

Get the exact triple Tauri expects for your machine with:
```bash
rustc -vV | grep host
```
