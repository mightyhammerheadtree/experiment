# x64-first EXE → browser workflow

Glassforge is a workbench around GEX, not a universal one-click converter.
The web interface creates analysis handoffs. The CLI build adapter requires
an already prepared GEX/Wine game recording and unit cache. No successful
Ichorous browser execution or end-to-end GEX build is claimed yet.

## 1. Install and inspect (no guest execution)

Python 3.10+:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m forge inspect /path/to/game/Game.exe
python -m forge plan /path/to/game/Game.exe --discover --budget 100000
python -m forge handoff /path/to/game/Game.exe --discover -o work/analysis.zip
python -m forge serve
```

Use http://localhost:8080 when running locally. Remote preview is available from
the development environment. The service binds to 0.0.0.0; treat it as a local,
trusted-user tool, not a hardened public upload service. Do not expose it to
untrusted users. Files are uploaded to the Python server, held temporarily, and
not executed. There is no authentication, per-user quota, or process sandbox.

Keep all game assets beside the EXE. `data.win` and audio groups indicate a
GameMaker distribution; the EXE alone is not enough. Discovery uses iced-x86
for instruction decoding and PE entry/export/x64 unwind information as seeds.
It does not prove exhaustive coverage or resolve all indirect branches.

## 2. Prepare upstream GEX on a separate build machine/VM

```sh
git clone https://github.com/HeyPuter/gex /path/to/gex
cd /path/to/gex
git checkout 9004980758dbba3f16fa40db7dbc69cc4a9a2eb9
```

Follow that checkout's README, wine/README.md, page/README.md and implementation
in crates/gex-eject/src/wine32.rs. Prerequisites include Rust 1.96.0, LLVM 22,
Node 22, Emscripten, wasm-tools, MinGW-w64 GCC 12 and native build dependencies.
Build GEX's x86 driver, Wine and browser runtime following upstream targets:

```sh
make gexc wine page
```

This is a starting point, **not** a complete per-game preparation command.
The x64 page also needs memory64 artifacts when applicable (upstream source
identifies `GEX_MEM64=1 hosts/browser/build.sh`), NT64 trampoline units,
precompiled image units, a Wine prefix/bundle and the appropriate graphics
components. Use the upstream Wine and page scripts for these, rather than
hand-implementing their ABI. Run `python -m forge doctor --gex /path/to/gex`
from this repo to identify missing tools/artifacts; presence is not a version
or compatibility certification.

### Important upstream naming trap

The documentation and filenames often say “wine32”, but the pinned source
contains `KIND64 = "wine64"`, detects Wine's `/x86_64-unix/` loader, includes
memory64 runtime modules and NT64 trampolines, and carries D3D state into its
launch manifest. Both x64 and x86 use `wine32-session.json` and
`build/web/wine32.json`. Do **not** rename these files or reject x64 merely
because of that name. This has been source-reviewed, not end-to-end validated.

The source at this pinned commit is more current than portions of its README.
See docs/x64-integration.md for precise source locations and remaining work.

## 3. Prepare a game page and record real gameplay

Prepare a GEX Wine page/bundle whose launch uses the correct Wine loader and
includes the EXE **and all assets**. This step is manual today. Merely making a
tar of the EXE is insufficient. Build the necessary unit cache using upstream
GEX cgen/units tooling; see wine32.rs's diagnostics for trampoline requirements.

From the GEX checkout, for an already prepared site and bundle:

```sh
node site/record-wine32.mjs http://127.0.0.1:8000/ /absolute/recording \
  --serve /absolute/prepared-game-site --bundle /absolute/game-bundle \
  --title Ichorous --settle 30
```

This URL belongs to the recording machine, not the user's remote browser.
The upstream recorder launches Chromium with sandbox-disabling flags; run it
inside a disposable VM. A window/title appearing is not full gameplay coverage.
Use upstream recording options to exercise menus, levels, saves, audio and
other paths. Static discovery alone cannot guarantee coverage. Guest-generated
code may fundamentally require JIT and fail a strict static-only target.

## 4. Eject, compile, package (x64 default)

From this repository:

```sh
python -m forge build --arch x64 --gex /path/to/gex \
  --recording /absolute/recording --unit-cache /absolute/unit-cache \
  -o /absolute/new-output-directory
```

For a recorded x86 project, use `--arch x86`.

The adapter verifies the pinned checkout, passes `--web-src` and optional unit
cache to GEX eject, checks the ejected project's architecture, and sets:

```json
{
  "features": {"translation": false},
  "cold": "none",
  "bundle": "whole",
  "resources": "whole",
  "helpers": "keep",
  "start": {"filesystem": "memory"}
}
```

This conservative baseline avoids prematurely trimming resources or putting
cold code behind a JIT. GEX itself rejects recorded addresses absent from its
compiled units in an AOT-only build. The adapter then checks the built launch
manifest's kind, disabled translation and nonempty unit list; invokes upstream
eject-site; and writes browser-build.zip with a hashed glassforge-build.json.
**These checks are not proof of successful or complete gameplay.**

Build execution is intentionally CLI-only; the upload server cannot invoke it.
Failed builds leave command history and output for diagnosis. Retry using a
new output directory. The build adapter is covered by orchestration tests with
mocked upstream processes, not a successful real toolchain build in this sandbox.
This environment has no Rust/clang and cannot fetch every required build host.

## 5. Validate before publishing

Extract browser-build.zip and use its upstream `node serve.mjs`. Opening
index.html with file:// is not sufficient. Production hosting must send COOP
and COEP headers (see generated `_headers` and README). Test WebGPU and any
required memory64 browser support. Play all important paths and inspect traps.
Record/rebuild missing code; never silently enable JIT to declare static success.

The generated in-memory filesystem does not persist saves across reloads.
Configure supported OPFS storage deliberately after baseline validation.
Review GEX's AGPL obligations, Wine/third-party licenses and game redistribution
rights before publishing binaries or assets.

## Optional Qubes isolation

Use an operator-created disposable qube with no personal files or secrets and
no network while handling the EXE. Fetch/build dependencies separately. Use
Qubes' documented file-copy facilities to transfer only needed game inputs and
inspect exported artifacts in another qube. No Qubes automation or security
guarantee is implemented. Containers and temporary directories are not VM
isolation boundaries. Qubes is not a decompiler or translation backend.
