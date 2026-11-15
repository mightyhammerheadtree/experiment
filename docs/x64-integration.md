# x64 integration: findings, implementation and remaining gates

Source reviewed at GEX `9004980758dbba3f16fa40db7dbc69cc4a9a2eb9`.

## Existing upstream mechanisms we will reuse

- `crates/gex-eject/src/wine32.rs`: `KIND64`, `is_wine64`, `runtime_wasm`,
  `trampolines64`, `aot_only`, `build`. The historical module name is not its
  complete architecture scope. wine64 detection examines the page's loader
  path for `/x86_64-unix/`.
- The same module's launch generation writes `kind`, `d3d`, extended attributes,
  `features_off` and units into **wine32.json for both architectures**.
- `site/eject-site.mjs`: consumes that manifest, writes the static site and
  site.json, including the launch's kind and features_off. The header comment
  and initial error message still describe only 32-bit projects.
- `page/src/app.js`: consumes memory64 and D3D launch state.
- `site/record-wine32.mjs`: collects a page session and worker/unit diagnostics.
  It launches a browser, not an AOT compiler. Recording still needs a prepared
  game page, Wine filesystem and compiled units.

## Implemented in Glassforge

1. x64 default build target, x86 second; pefile metadata parsing.
2. iced-x86 bounded recursive code discovery from entry/export/unwind seeds.
3. Compatibility checkpoints for imported graphics, audio, network and .NET APIs.
4. Correct eject invocation with web source and explicitly checked unit-cache path.
5. Ejected model architecture gate before building.
6. Explicit `features.translation=false`, `cold=none` (the generic
   `jit_fallback` setting alone is not the Wine-page AOT switch).
7. Built launch and packaged site kind/translation checks; nonempty units.
8. Static ZIP with source revision, SHA-256 file inventory and the honest status
   `built-not-gameplay-validated`.
9. Non-executing recording preflight: source revision/cleanliness, runtime
   modules, session format/loader architecture, bundle and recorded unit pairs.
10. Streamed ZIP integrity verification before returning a browser build.
11. Opt-in pinned upstream setup plans with logs and a provisioned-runner workflow.
12. Opt-in upstream Wine page probing through a local BENCH_SH adapter; no custom
    bundler or instruction semantics implementation. Probe != AOT export.

## Ichorous sample

Input repo: https://github.com/mightyhammerheadtree/ichorousport

Revision: `141098993f0043ca676610883c2850470f22c165`, directory `raw/`.
The EXE is x64, 28,524,544 bytes; data.win indicates GameMaker, and d3d11.dll
is imported. Checked without running the EXE. A 100,000-instruction bounded
analysis reached the budget limit, so it is explicitly not full code coverage.
The companion files total roughly 29 MiB and include data.win, audio groups,
localization and configuration. See sample-analysis.json for reproducible facts.

## Acceptance gates still open

- Install the full upstream toolchain and build Wine64, page, memory64 runtime,
  NT64 trampoline providers and the game's image units.
- Assemble a correct x64 Wine launch/bundle including assets and validate D3D11.
- Record startup and gameplay; prove the expected wine64 model is emitted.
- Run the actual strict-AOT build/export path, not mocked process tests.
- Test browser startup, interaction, sound, levels and saves. Fail missing-code
  paths and expand coverage. Investigate any GameMaker-generated code requiring
  runtime translation; do not relabel that as static.
- Repeat the same pipeline with x86 regression fixtures/real games.

This is not yet “GEX on steroids” in compatibility or performance. It is a
reuse-first orchestration and diagnostics layer, with those goals gated on
measured end-to-end results rather than assumptions.
