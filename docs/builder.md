# Build-machine setup, upstream probing and export checks

These commands make the integration reproducible; they have not yet produced a
real Ichorous AOT export. The sandbox can test planning, validation and command
orchestration, but does not have the full toolchain or a provisioned runner.

## 1. Review a build plan

```sh
python -m forge setup --gex /build/gex --phase all --jobs 4
```

This prints JSON commands without cloning, building, or installing anything.
If the path is absent, the execution plan clones GEX and checks out the exact
reviewed commit. Existing paths must be Git checkouts; execution requires the
pinned revision and no tracked modifications. No existing source is reset,
overwritten or silently upgraded. Untracked build outputs are allowed.

Available phases:

| Phase | Upstream operations |
| --- | --- |
| fetch | Clone and pin if absent; validate an existing checkout |
| driver | Build only the x86-feature gexc driver with Cargo.lock |
| wine | `make wine`, Wine64/WoW64 and prefix |
| runtime | `make page`, then x86 memory64 browser shim |
| all | driver, wine, page, memory64 |

The operator must provision compatible Rust 1.96.0 and the nightly/rust-src
components upstream uses, clang/LLVM 22, Node >=22, Emscripten **6.0.1**, MinGW
GCC **12**, wasm-tools, zstd, native build tools, Chromium, graphics drivers and
other upstream dependencies. Consult pinned GEX's own documentation/scripts.
`doctor` reports presence, not version conformance. Do not assume a stock hosted
Ubuntu image contains these versions or enough disk/RAM.

After reviewing the plan on a capable machine:

```sh
python -m forge setup --gex /build/gex --phase all --jobs 4 \
  --execute --logs /build/logs/setup-01
```

Logs must go to a new directory. Each upstream command gets a log; plan.json
and status.json retain the completed/failed steps. No OS package installation,
sudo, or remote install script is performed by Glassforge. Setup does not use a
shell to interpret its argument arrays. It does execute trusted upstream build
scripts, which may fetch their own dependencies and execute build tools.
Network access to GitHub alone is not sufficient: upstream fetches from hosts
including musl.cc and busybox.net and toolchain installers need other servers.

## 2. Probe the game using upstream preparation

Use an isolated VM with no credentials or personal files. The upstream page
harness starts Chromium with sandbox-disabling flags. A Python subprocess or a
container alone is not a security boundary for untrusted programs.

After `make wine`, use the paths written by GEX to out/wine.env. In a shell:

```sh
. /build/gex/out/wine.env
python -m forge probe /games/Ichorous/Ichorous.exe \
  --gex /build/gex --dist "$WINE64_DIST" --prefix "$WINE64_PREFIX" \
  --unit-cache /build/game-units --build-units \
  --seconds 120 -o /build/probes/ichorous-01
```

This prints a plan. Add `--execute` only after reviewing it. Execution checks
GEX's revision/source cleanliness and rechecks the EXE hash before running.
The local bench adapter accepts upstream's `-s DIR ... -- COMMAND` contract,
checks directories exist, and executes the command directly without syncing it
to another host. It does not emulate a GPU or provision a browser.

GEX's existing `wine/run.sh --page` creates a run tree, stages Wine, copies a
prefix, bundles the game directory and can invoke its unit builder. Glassforge
sets WINE32_PAGE_DIR under the new output path, so probe artifacts are retained
there alongside probe-plan.json, probe.log and probe-status.json. The unit cache
is shared explicitly for repeated passes; choose a new probe output each time.

**Put only game inputs in the EXE's parent directory.** Upstream bundles that
entire directory, including any unrelated or sensitive files. Output inside
the game directory is rejected to avoid recursive inclusion. The probe path is
runtime translation for collecting compatibility/unit information, not a static
recompilation. `--build-units` may require multiple passes and does not establish
full gameplay coverage. An upstream failure keeps available logs/artifacts.

The upstream probe path is source-reviewed and tested with mocked processes.
It has not been exercised with the real Wine64/browser toolchain here. In
particular, converting its split bundles/run tree into the single-bundle,
recording-ready page expected by the eject recorder is still an open step.
Do not feed probe-status.json into `forge build` as if it were a recording.

## 3. Preflight a real recording

After producing wine32-session.json using GEX's recorder (the same legacy
filename is used for x64):

```sh
python -m forge preflight --gex /build/gex --arch x64 \
  --recording /build/recording --unit-cache /build/game-units
```

Exit 1 means blocked; JSON lists individual failures. Checks include the pinned
clean checkout, GEX files and x64 runtime modules, session format, loader
architecture, an existing **absolute** bundle path, 64-hex-digit unit keys and
recorded unit c.wasm/c.entries pairs. It does not guess missing cache paths or
rewrite recordings. Coverage misses are warnings because the upstream eject
performs the authoritative address/unit checks. GEX also validates NT
trampoline/provider keys that this preflight cannot derive.

An x86 executable on WoW64 still uses a wine64 loader/project. The current
`--arch x86` build contract means a wine32 model, not arbitrary x86-on-WoW64;
preflight deliberately flags that distinction rather than guessing.

`forge build` runs these checks automatically before creating its output tree.
Then use the strict export commands in [workflow.md](workflow.md).

## 4. Verify the resulting ZIP

```sh
python -m forge verify /build/port/browser-build.zip
```

This streams hashes without extraction. It rejects missing/extra files,
modified hashes, duplicate members, traversal/noncanonical paths, symlinks and
oversized archives (16 GiB uncompressed limit). It cross-checks architecture and
declared translation-off settings. `verified-integrity-only` does **not** mean
authentic, safe, valid Wasm, or playable. The manifest is unsigned: an attacker
who rewrites both files and hashes can forge its claims. Sign/distribute through
a separate trusted release process if authenticity is needed.

## Optional GitHub Actions runner

`.github/workflows/gex-builder.yml` is manual-only (`workflow_dispatch`) and
requires a self-hosted runner labelled `linux`, `x64`, **`gex-builder`**. It does
not install or register a runner. Without one, dispatching the workflow queues
instead of building. It defaults to the driver phase and never downloads a
game. Build logs—not game assets or runtime distributions—are uploaded for seven
days. No workflow has been dispatched as part of this implementation.

Use a dedicated disposable runner with adequate resources, the above versions
and network access. Never attach an unrestricted public-repo runner to a
personal workstation; review which repository users can dispatch/run code and
use runner groups/repository access controls. The workflow serializes its jobs
and has a six-hour timeout, which does not guarantee an all-phase build will fit.
