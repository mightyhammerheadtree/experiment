# Glassforge

**An x64-first, x86-second Windows-to-browser port workbench built around GEX.**

Reuse the translator. Make preparation, compatibility diagnostics, strict-AOT
settings and export verification easier. No homemade CPU emulator.

> **Current status:** working inspection, code discovery, web workbench and
> analysis ZIP export. A source-reviewed GEX x64/x86 build adapter is implemented
> and orchestration-tested, but has **not** completed a real GEX build or produced
> a verified playable Ichorous port. A bare EXE is not yet an all-in-one input
> for playable output. Wine bundle/unit-cache preparation remains manual.

## Run

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m forge serve
```

Open http://localhost:8080 locally, or use your environment's live preview.
Select one EXE plus companion files. The UI reports architecture, imported DLLs,
compatibility checkpoints and a bounded iced-x86 instruction preview. Its ZIP is
clearly labelled **analysis only**, not a fake browser conversion.
Uploads go to the Python server temporarily; no uploaded executable is run.
This is a trusted-user development server, not a hardened public upload service.

## CLI

```sh
python -m forge inspect /games/Ichorous.exe
python -m forge plan /games/Ichorous.exe --discover --budget 100000
python -m forge handoff /games/Ichorous.exe --discover -o work/analysis.zip
python -m forge doctor --gex /path/to/gex

# Requires prepared upstream Wine page/bundle, gameplay recording and units:
python -m forge build --arch x64 --gex /path/to/gex \
  --recording /path/to/recording --unit-cache /path/to/units -o work/port
```

The build defaults to x64. Use `--arch x86` for a recorded 32-bit project.
The adapter enforces GEX `features.translation=false` and `cold=none`, checks
architecture and launch settings, and packages upstream output with file hashes.
Its output status is **built-not-gameplay-validated**, not “works everywhere”.

## Documentation

- [Complete workflow and prerequisites](docs/workflow.md)
- [x64 source integration and remaining acceptance gates](docs/x64-integration.md)
- [Existing projects evaluated, including Bochs](docs/upstream-research.md)
- [Ichorous analysis summary](docs/sample-analysis.json)

GEX's filenames and documentation can be misleading: the pinned source's
`wine32.rs` also supports `wine64`, and both use `wine32-session.json`.
Qubes OS is an optional disposable-VM environment, not a decompiler. Bochs is a
reference for accurate emulation, not an EXE-to-static-Wasm compiler.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests include synthetic x64/x86 PE files, branch/call discovery, malformed
inputs, budget limits, upload validation, strict-AOT rejection and mocked x64
build orchestration. They do not establish game or upstream runtime compatibility.

## Licensing and distribution

No GEX/Bochs implementation source is vendored. Python dependencies are pinned
in requirements.txt. GEX is AGPL-3.0-only; its runtime and third-party components
retain their licenses. Review corresponding-source/notice obligations and game
asset redistribution rights before publishing a port. Analysis archives do not
bundle the game executable or its assets.
