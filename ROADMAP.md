# Windex roadmap and local-agent handoff

**Priority: build compatible Wasm Wine → integrate the complete browser runtime → validate runtime behavior → test games.**

Windex is an **in-browser x86/x64 Windows runtime**, not a CLI or a per-game conversion tool:

```text
Local EXE + companion files
    → Wine Windows APIs
    → GEX x86/x64 runtime translation + Linux ABI
    → WebAssembly + browser graphics/audio/input
```

This document is the handoff for the on-device agent compiling Wine, and the integration plan for the agent receiving its artifacts. Build commands below are developer operations, not the Windex user interface.

## 1. Where we are

- The browser application, game-folder import, GEX adapter, Wine-layer installer and Wine execution-test controls exist.
- Real GEX + Wasm Debian boot was verified in Chromium in the preceding work. It correctly reached **Needs Wine**. This is not Windows execution.
- **Next required artifact: the GEX-compatible Wine64/WoW64 distribution and its matching initialized win64 prefix.** Debian alone does not include these.
- No Wine execution, end-to-end graphics compatibility, or game compatibility has been established.
- The current checkout does **not** contain `scripts/build-wine.py` or `windex/wine_bundle.py`. Do not assume those helpers exist from an earlier conversation; use the pinned upstream build below.
- The current Wine readiness check expects bare Wasm, and the adapter forces memory64 for x64 launches. Both need correction during integration: upstream can package Wasm in a special ELF envelope, and its default lowered Wine build does not require memory64 merely because the Windows program is x64.

## 2. Boxedwine investigation: can we reuse its Wine?

Reviewed [danoon2/Boxedwine](https://github.com/danoon2/Boxedwine) at commit **`349c63d4c81e7422db4cad42500e38638a57785d`**. Findings below describe that revision, not every release.

### What is similar

Boxedwine combines Wine, CPU emulation, a Linux compatibility environment, and a browser build. Its packaging, browser JIT work, compatibility patches and test organization are valuable references.

### Its Wine build is not the same as GEX Wasm Wine

| Question | Finding / consequence for Windex |
| --- | --- |
| What Wine does Boxedwine target? | Its documented model is **32-bit x86 Wine**, running 16/32-bit Windows programs. Native x64/ARM64 host builds do not imply x64 Windows guest support. |
| Is its Wine simply compiled to browser Wasm? | Its filesystem builder packages Wine and Linux runtime libraries for the emulated x86 environment. Boxedwine's emulator is compiled for the browser. That is different from GEX's native Wasm Wine build. |
| What else does the filesystem contain? | Its current Wine 11 filesystem builder uses a pinned TinyCore base, Boxedwine Linux graphics libraries, Wine patches, and add-ons. A “Wine filesystem ZIP” is not just a loader or standalone Wasm module. |
| Can we drop that ZIP into Windex? | **Not as the current GEX-native Wine layer.** Archive layout, prefix, guest libraries, graphics bridges and loader assumptions differ. Renaming ZIP to TAR or copying DLLs does not resolve those differences. |
| Could GEX execute its x86 Wine instead? | Potentially a separate experiment, since GEX supports x86 Linux executables. This would require auditing the ELF/libc/syscall/graphics dependencies and testing the complete guest environment. It is **not verified**, is not the selected Wasm Wine build path, and does not by itself solve x64 Windows support. |
| Can we reuse patches or ideas? | Yes, after checking applicability, ABI assumptions and licensing. Study the build manifests, audio/graphics patches, JIT batching and cache lifecycle. Do not blindly mix DLLs or prefixes between builds. |

**Decision:** keep **GEX + its pinned Wine fork** as the primary x86/x64 architecture. Do not ask the local agent to compile Boxedwine's Wine in place of it. Keep a Boxedwine-based 32-bit backend or an x86-Wine-on-GEX experiment as an optional, separately scoped investigation—not a replacement silently added to the main runtime.

### Important JIT finding

Boxedwine's README still calls Web JIT a TODO, but its source at the reviewed revision contains:

- `source/emulation/cpu/wasm/jitWasmCodeGen.cpp`;
- Emscripten `jit`, `multiThreadedJit`, `testJit`, and `testMultiThreadedJit` build targets;
- a Wasm-module broker and cache/optimization tooling.

Its makefile describes emitting basic blocks as Wasm modules and optionally merging them into bounded groups. This is stronger evidence of implementation work than the older README TODO, but **we have not built or benchmarked it**. Native x86/ARM machine-code JIT backends cannot simply execute inside the browser; browser-side guest translation must emit Wasm or another browser-permitted representation.

Pinned references:

- [Boxedwine README](https://github.com/danoon2/Boxedwine/blob/349c63d4c81e7422db4cad42500e38638a57785d/README.md)
- [CPU architecture](https://github.com/danoon2/Boxedwine/blob/349c63d4c81e7422db4cad42500e38638a57785d/docs/CPUemulation.md)
- [Current Wine/filesystem builder](https://github.com/danoon2/Boxedwine/blob/349c63d4c81e7422db4cad42500e38638a57785d/tools/buildWine/README.md)
- [Wine filesystem profile](https://github.com/danoon2/Boxedwine/blob/349c63d4c81e7422db4cad42500e38638a57785d/tools/buildWine/filesystem_wine11.json)
- [Browser JIT build targets](https://github.com/danoon2/Boxedwine/blob/349c63d4c81e7422db4cad42500e38638a57785d/project/emscripten/makefile)
- [Wasm JIT backend](https://github.com/danoon2/Boxedwine/blob/349c63d4c81e7422db4cad42500e38638a57785d/source/emulation/cpu/wasm/jitWasmCodeGen.cpp)

## 3. NEXT: local agent builds GEX Wasm Wine

### Exactly how much of Wine?

**Build the complete upstream default Wine64 + WoW64 runtime distribution—not just `wine`, `ntdll`, or a few DLLs.** We need broad Windows API coverage and all dependencies the upstream runtime build stages. Start with the complete known upstream output; size reduction comes after it works.

“Complete runtime” does **not** mean every Wine source file becomes one huge Wasm file, every optional Wine feature is available, or all build tools must ship to the browser.

| Component | Required handoff |
| --- | --- |
| Unix side | GEX-targeted Wine64 loader, matching wineserver, Unix-side libraries and drivers staged by upstream. The wineserver uses its own upstream wasm32 build path. |
| Windows API side | The full upstream installed x86_64 Windows DLL/program set, including PE skeletons and associated native Wasm modules where generated. Keep sidecars, core modules, metadata and relative paths together. |
| x86 support | WoW64 bridge plus upstream i386 Windows DLLs. These may still contain x86 code translated by GEX; not every DLL is necessarily native Wasm. |
| Display, sound and input | Keep the upstream staged Wayland/OpenGL, audio and controller components. Their browser-host integration must subsequently be verified; a successful compile does not prove D3D11 or Vulkan support. |
| Runtime data | Wine configuration/INF files, registry support data, fonts and other staged runtime resources. |
| Prefix | A **matching initialized win64 prefix**, with both system32/syswow64 as produced, registry files, C: and Z: mappings, and browser-safe user directories. |
| Build tools | Keep compilers, source trees, objects, native build utilities and caches on the build machine. They are not browser runtime payload. Preserve source/build records for reproducibility and licensing. |

Do **not** add stock Linux Wine packages, random DLL downloads, DXVK, Gecko, Mono or an unrelated prefix to “complete” the build. Those need separate compatibility work. The pinned GEX Wine README documents Gecko/Mono and media gaps; optional media/controller behavior must be checked against the pinned build scripts and recorded in the handoff. Do not promise all of Wine's optional functionality.

### Source pins

Use the values in `upstreams.lock.json` and verify them before starting:

```text
GEX repository: https://github.com/HeyPuter/gex
GEX revision:   9004980758dbba3f16fa40db7dbc69cc4a9a2eb9
Wine fork:      https://github.com/MercuryWorkshop/wine-wasm
Wine64 commit:  1395ef351a40df15260b7969ef6c3e88e0665e91
```

Let that GEX revision fetch the other sources from **its own** pins. For example, its `wine/wine.pins` also selects a separate 32-bit Wine revision for the wineserver. Do not replace it with the Wine64 commit or use the latest Wine branch indiscriminately.

The published `@gexemu/runtime@1.0.0` currently used by Windex is **not proven ABI-identical** to that GEX source revision. If necessary, we will also need a compiled browser runtime from the same source as Wine. Keep a record of this boundary rather than declaring the npm runtime compatible.

### Local build instructions

Prefer a Linux x86-64 machine, or a suitably provisioned Linux VM/WSL environment with a Linux filesystem. Follow the pinned upstream prerequisite documentation, including:

- LLVM/clang/wasm-ld **22**, LLVM development headers and associated tools;
- Rust toolchain from upstream `rust-toolchain.toml` (**1.96.0** at this pin);
- MinGW-w64 GCC **12** for **both** x86_64 and i686;
- Node **22+**, Python, make, standard native development tools and Linux UAPI headers;
- compiler-rt builtins sources, via `GEX_CRT_SRC` if not found in upstream's expected SDK locations;
- any additional native tools/development packages requested by the upstream dependency builds.

These are prerequisites, not a complete distro-specific package installation recipe. The agent should capture missing dependencies and failures in its build log rather than bypassing them with stock binaries.

```sh
# Developer build machine only. Start with a fresh destination.
git clone https://github.com/HeyPuter/gex gex-wine-build
cd gex-wine-build
git checkout 9004980758dbba3f16fa40db7dbc69cc4a9a2eb9

# Provision upstream prerequisites first.
# Set GEX_CRT_SRC=/absolute/path/to/compiler-rt/lib/builtins if needed.
set -o pipefail
WINE64_MEM64=0 WINE64_TWIN=0 make wine 2>&1 | tee windex-wine-build.log
```

Run this in Bash. Use `make wine`, **not** `make wine-x64` (omits WoW64) and **not** legacy `make wine32`. The selected first profile is the default lowered-memory Wine build; do not independently turn on memory64 or mix its modules into this output.

Upstream prints and saves build paths in `out/wine.env`, including:

```text
WINE64_DIST=...      # complete installed distribution
WINE64_PREFIX=...    # initialized matching prefix
WINE64_NATIVE=...    # build output/reference; do not copy only this
```

Read [the pinned upstream Wine instructions](https://github.com/HeyPuter/gex/blob/9004980758dbba3f16fa40db7dbc69cc4a9a2eb9/wine/README.md) and [its Wine pins](https://github.com/HeyPuter/gex/blob/9004980758dbba3f16fa40db7dbc69cc4a9a2eb9/wine/wine.pins). Its estimate of about 40 minutes on 16 threads is upstream guidance, **not a Windex build measurement**; downloads, machine speed and failures can make it much longer.

### Package for Windex: one matched distribution + prefix

Use the upstream `wine/page-prefix.sh` to prepare the prefix. Do not tar a live personal `~/.wine`; it can contain host links, user data and registry paths that do not belong in a browser.

Example after the upstream build, in the same trusted source checkout:

```sh
# out/wine.env is generated by YOUR trusted upstream build.
. out/wine.env

# Choose a NEW staging location; retain the original build outputs.
mkdir -p windex-package
cp -a "$WINE64_DIST" windex-package/wine
DIST_MOUNT=/wine GRAPHICS=wayland bash wine/page-prefix.sh \
  "$WINE64_PREFIX" "$WINE64_DIST" "$PWD/windex-package/pfx"

# Preserve symlinks. NEVER use tar -h / --dereference: Z: points to /.
tar -C windex-package -cf windex-wine.tar wine pfx

# Optional compression; Windex accepts .tar or .tar.zst, not ZIP or .tar.gz.
zstd -T0 -10 -k windex-wine.tar -o windex-wine.tar.zst
sha256sum windex-wine.tar.zst
stat -c '%s' windex-wine.tar.zst
du -sh windex-package/wine windex-package/pfx
```

If zstd is unavailable, return the uncompressed `.tar` and its checksum instead. Inspect archive entries without extracting untrusted archives on the host. Confirm no build-host paths or personal data escaped prefix preparation. Preserve `dosdevices/c:` and `dosdevices/z:` as links; do not follow Z: while packaging or measuring.

Expected guest layout (not an exhaustive file list):

```text
/wine/lib/wine/x86_64-unix/wine
/wine/lib/wine/x86_64-unix/wineserver
/wine/lib/wine/x86_64-windows/ntdll.dll
/wine/lib/wine/x86_64-windows/kernel32.dll
/wine/lib/wine/i386-windows/ntdll.dll
/wine/... all other staged DLLs, modules, drivers, data and fonts ...
/pfx/system.reg                  # #arch=win64
/pfx/user.reg
/pfx/drive_c/...
/pfx/dosdevices/c:               # resolves to drive_c
/pfx/dosdevices/z:               # maps to /
```

**Do not “fix” an ELF-looking Wine loader by replacing it with a raw `.wasm` sidecar.** Upstream `wcc64` can wrap its Wasm program in an ELF64 x86-64 container with a `GEXWASM` header. This is distinct from stock Linux ELF Wine. Windex needs to recognize the upstream format during integration.

### What the on-device agent should return

- [ ] `windex-wine.tar.zst` (or `.tar`) with `wine/` and prepared `pfx/` at its root.
- [ ] `SHA256SUMS` and exact compressed/unpacked byte sizes, separately for distribution and prefix where practical.
- [ ] `BUILD-INFO.md`: host OS/CPU, source commits, dirty-tree status, compiler/tool versions, command/environment overrides, enabled/disabled features, and success/failure notes.
- [ ] Complete build log and the generated `out/wine.env` (redact private host paths if needed; do not include secrets).
- [ ] Copies of the source pin files and a record of every local patch. Keep source archives/locations and license/notice material available for redistribution obligations.
- [ ] If built, the **matching compiled GEX browser runtime**, clearly separate from Wine, with its revision and checksum. Do not substitute the Boxedwine emulator build.
- [ ] Report “compiled only” unless actual browser execution was performed. Do not claim game compatibility.

## 4. How big will Wasm Wine be?

**We do not have a compiled Windex Wine artifact yet, so an exact file size would be made up.** It is a directory of loaders, DLLs, Wasm modules, fonts/data and a prefix—not one small `wine.wasm` file.

Use these deliberately broad **planning estimates, not measured sizes or limits**:

| Item | Provisional budget |
| --- | --- |
| Compressed Wine64 + WoW64 distribution **and prepared prefix** | Approximately **100–500 MiB**, possibly more depending on modules, symbols, fonts, duplicated prefix files and optional libraries. |
| Unpacked distribution + prefix | Approximately **0.5–2 GiB**; verify with the actual build. |
| Local source, dependency downloads and build intermediates | Reserve roughly **30–60 GiB free disk** to start; this is separate from the downloadable runtime and can grow. |
| Browser RAM | Not inferable from archive size. Wasm memories, translated code, graphics allocations, filesystem and the application need separate measurement. |

Do not interpret the lower end as a promised download target. Debug symbols and duplicated files can significantly change the result. Measure first, then consider stripping **through supported upstream build options**, compression and lazy loading; do not randomly delete DLLs to hit a size target.

Boxedwine's published [26R1 Web ZIP](https://github.com/danoon2/Boxedwine/releases/tag/26R1.0) is listed by GitHub as **122,244,710 bytes (~116.6 MiB)**. That is a **different project's Web release archive**, not a measured GEX Wine bundle or a valid prediction of our final payload. Do not conflate the two.

Windex currently limits browser-selected runtime layers to **1 GiB combined archive bytes**. That is an implementation limit, not a Wine size estimate. If real artifacts exceed it, we must redesign loading/resource budgets rather than silently trimming essential runtime files.

### Putting artifacts “on the repo” safely

- Put the small `BUILD-INFO.md`, checksums, source pins and artifact location in a proposed `artifacts/wine/` metadata directory.
- Prefer a **GitHub Release asset** for the large archive, or deliberately configured Git LFS. A Release on this same repository still makes the files available to the integration agent.
- Do not commit build caches, `node_modules`, source/build trees, or a huge extracted prefix into ordinary Git. GitHub blocks individual ordinary Git files above 100 MiB, and large binary history is expensive even below that.
- Local staging under `work/` is already ignored. A suggested metadata directory is not an existing artifact downloader; receiving/staging the archive remains integration work.

## 5. Integration milestone: make all components work together

After the local build artifacts arrive, the integration agent should:

1. **Audit the handoff:** verify checksums, revisions, features, license material, archive paths/symlinks and the distribution/prefix pairing. Do not execute or extract untrusted files on the host without inspection.
2. **Fix loader validation:** accept the actual GEX Wasm/`GEXWASM` ELF envelope, reject unrelated ELF Wine, validate headers and bounds, and check the matching wineserver.
3. **Fix memory-profile selection:** use the supplied default lowered profile. An x64 Windows EXE does not automatically require Wasm memory64; memory64 needs its own matching loader/modules/runtime.
4. **Assemble the deployment:** mount Wasm Debian first, then Wine at `/wine` and the prepared prefix at `/pfx`; preserve files, modes, links and sidecars. Add reproducible bundle metadata/integrity handling rather than a manual DLL-copy recipe.
5. **Connect the runtime environment:** check `WINEPREFIX`, host display variables, WoW64 settings, wineserver startup/shared-state behavior, and the upstream environment required by the supplied build. Disable unnecessary periodic registry writes for disposable sessions where supported.
6. **Check browser services:** Wayland windows, graphics-provider initialization, input capture, audio initialization from a user gesture, filesystem imports, persistence/session reset and process cleanup.
7. **Validate Wine itself:** first `cmd.exe /c ver`, real stdout/stderr and exit status, timeout/termination, then small non-game x64/x86 probes for process, filesystem, display, audio and input. Structural file checks alone are not execution verification.
8. **Resolve ABI mismatches:** if npm GEX and source-built Wine disagree, rebuild/stage a matching GEX browser runtime. Do not paper over missing imports by mixing unrelated releases.

**Exit gate before games:** a reproducible combined deployment that executes Wine and focused x64/x86 runtime probes, reports real failures and can cleanly stop/reset. No claim that all Windows applications work.

## 6. MAJOR milestone: browser JIT integration and optimization

**JIT is a major implementation and performance workstream, not a checkbox or a promise that browser compilation alone makes games fast.**

There are two different levels:

1. **Guest translation JIT:** GEX translates x86/x64 guest instructions into Wasm at runtime. Windex already relies on that architecture; we are not starting with a CPU interpreter that has no dynamic translation.
2. **Browser engine compilation:** the browser compiles/optimizes Wasm for the user's CPU. This does not replace the first level and is largely controlled by the browser.

The pinned GEX source describes basic-block translation, a function JIT (`gex-fjit`), and a separate C/clang ahead-of-time tier (`gex-cgen`). Their existence upstream does **not** prove every tier is enabled, exposed, compatible or beneficial in the Windex deployment. Audit the exact built runtime first. Optional AOT must not become a mandatory per-game conversion step.

### Planned work

- [ ] **JIT audit and instrumentation:** identify active tiers, supported x86/x64 paths, configuration/public API boundaries, translation counts/time, module compilation latency and cache behavior. Do not invent unsupported runtime options.
- [ ] **Tiered hot-code optimization:** assess and integrate upstream function JIT/hotness policies where supported; retain a correct baseline path for cold, unsupported, dynamically loaded or self-modifying code.
- [ ] **Module batching and worker reuse:** study Boxedwine's Wasm block grouping, module broker, bounded publication and cache tooling. Adapt concepts to GEX's different ABI rather than copying a CPU backend wholesale.
- [ ] **Correct code-cache lifecycle:** invalidate on executable-memory changes; key persisted data by guest content, runtime/translator version, architecture and feature profile. Address stale code, cache poisoning/corruption and multi-thread synchronization before trusting speedups.
- [ ] **Persistent translation caching:** evaluate GEX's existing `xcache` integration (already requested by the adapter), measure whether it actually hits, implement bounded storage/eviction and graceful operation without OPFS. Persist only representations the platform/runtime can safely restore; browser `WebAssembly.Module` persistence is not universal.
- [ ] **Responsiveness and scheduling:** bound compilation bursts, keep heavy work off the UI thread, tune worker use, and measure audio underruns, UI stalls and memory—not just peak instruction throughput.
- [ ] **Performance controls and diagnostics:** expose supported balanced/compatibility/performance settings in the browser, capability failures and resettable diagnostics. Never silently disable correctness checks to claim better FPS.
- [ ] **Regression gates:** focused instruction, threading, self-modifying-code and deterministic synthetic workloads; cold/warm startup, throughput, compilation time, peak memory and cache hit rate. Track correctness alongside speed.

**Order:** build/verify Wine and establish runtime correctness first; run JIT discovery/instrumentation in parallel where possible; then implement and benchmark optimizations. Focused non-game probes come before game tests. No guaranteed speedup or FPS number until measured.

Reference: [GEX's documented translation tiers](https://github.com/HeyPuter/gex/blob/9004980758dbba3f16fa40db7dbc69cc4a9a2eb9/README.md). Boxedwine references are in section 2. Review license compatibility before importing any source; a reference is not permission to discard notices or copyleft obligations.

## 7. Only afterward: game compatibility

- Import the complete `raw/` assets from the intended Ichorous example, not its EXE alone.
- Validate x64 loading and graphics requirements before claiming gameplay. Follow with a separate x86 game once WoW64 probes pass.
- Record browser/device, runtime/Wine revisions, required assets, graphics/audio/input behavior, cold/warm timings and reproducible failures.
- Keep a compatibility matrix: “imports,” “Wine starts,” “window renders,” and “playable” are different milestones.
- Optimize runtime size/loading and JIT using evidence; keep one reusable browser runtime rather than returning to per-game port generation.

**Immediate next action for the local agent:** build and return the pinned **GEX Wine64 + WoW64 distribution plus prepared matching prefix**, with checksums, sizes and build records. Do not start by building Boxedwine's Wine or testing games.
