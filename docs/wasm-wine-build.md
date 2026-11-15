# Wasm Wine build and browser integration

This is deployment engineering, not an end-user CLI or a game conversion step.
The browser remains the Windex runtime. No game testing is part of this stage.

## Source contract

Windex uses GEX's upstream Wine build rather than attempting to port stock Wine
independently. `upstreams.lock.json` pins GEX at
`9004980758dbba3f16fa40db7dbc69cc4a9a2eb9` and its Wine64 fork at
`1395ef351a40df15260b7969ef6c3e88e0665e91`. Upstream also pins the separate
wasm32 wineserver source, musl forks and dependency archives in `wine/wine.pins`,
`toolchain/pins`, and `wine/libs.pins`.

The loader is **not necessarily a bare Wasm file**. Upstream `wine/wcc64` emits
an ELF64 x86-64 envelope with a mapped `GEXWASM` header identifying its embedded
Wasm module. Windex checks that header's version, guest-x64 flag and mapped
module bounds; an ordinary Linux Wine ELF does not satisfy that contract.
Readiness checks remain structural, not an ABI or code-authenticity proof.

The default upstream build lowers LP64 Wine to wasm32 memory indexing while
retaining its x64 guest ABI. **An x64 EXE does not itself imply Wasm memory64.**
Windex therefore defaults to the lowered profile (`GEX_MEM64=0`). A deployment
that explicitly selects a memory64 profile must provide a matching memory64
Wine loader and modules and set `gex.memory64`; toggling this environment flag
alone cannot convert the binaries. The standard bundle packager produces the
lowered profile, not a twin/memory64 distribution.

## Build host

Use a sufficiently provisioned Linux x86-64 build machine with unrestricted
access to upstream dependency hosts. Upstream estimates about 40 minutes on
16 threads; this has not been measured for Windex.

Required upstream tools include LLVM/clang/wasm-ld **22** (with plugin development
headers), Rust **1.96.0**, Node **22+**, MinGW-w64 GCC **12** for both x86_64 and
i686, make, Python, pkg-config, bison/flex, standard native build tools, and
compiler-rt builtins sources (`GEX_CRT_SRC`). The upstream sysroot scripts also
require the host Linux UAPI headers. Library builds may require further native
tools; the preflight is an early prerequisite check, not a hermetic build image.

```sh
git clone https://github.com/HeyPuter/gex .cache/gex
git -C .cache/gex checkout 9004980758dbba3f16fa40db7dbc69cc4a9a2eb9
# Provision the tools above; set GEX_CRT_SRC to compiler-rt/lib/builtins.
python3 scripts/build-wine.py --check
python3 scripts/build-wine.py
```

The internal driver verifies a clean pinned source, runs upstream `make wine`
(Wine64 + WoW64), then reads `out/wine.env` as **data**, never shell-evaluating it.
For an existing completed upstream build use `--package-only`. Outputs must be
new subdirectories under ignored `work/`; existing bundles are not overwritten.

## Packaging and deployment

The packager checks the required loader/server/DLL/prefix outputs and invokes
upstream `wine/page-prefix.sh` with `DIST_MOUNT=/wine` and Wayland graphics.
That upstream step sanitizes host-user links, rewrites registry install paths,
checks matching builtins and prepares C:/Z: mappings. The distribution is mounted
at `/wine` and the prepared prefix at `/pfx` in **one** `windex-wine.tar` layer.
A companion `wine-bundle.json` records source revisions, SHA-256, size, mount
contract and an explicitly not-execution-verified status. Preserve the complete
upstream source/build records and required licenses when redistributing; the
manifest is not a substitute for corresponding source or licensing review.

To deploy all components together, put this in `windex.build.local.json`:

```json
{
  "runtime": "node_modules/@gexemu/runtime",
  "trees": ["node_modules/@gexemu/debian/debian-slim.tar.zst"],
  "wineBundle": "work/wine-bundle"
}
```

`npm run build` verifies the archive's SHA-256/size and mount contract before
appending it after Debian in the filesystem layers. It includes the bundle
manifest alongside the browser deployment. Alternatively select the tar through
**Install Wine** in the browser. Local tar installation does not verify the
companion manifest; install trusted layers only.

**ABI caveat:** published npm GEX and the pinned GEX source are not proven to
match. After building Wine, the first integration gate is `Test Wine`, not a game.
If the npm runtime is incompatible, supply the matching compiled runtime via the
`runtime` build setting. Do not declare the combination ready from a file check.

## Gate before games

1. Produce and package a real Wine64/WoW64 build with its matching prefix.
2. Assemble Debian + Wine + browser runtime in one deployment.
3. Confirm real browser kernel mount and structural Wine checks.
4. Run `cmd.exe /c ver`; require actual successful exit and inspect its logs.
5. Validate process lifecycle, Wayland display, audio/input and persistence with
   focused runtime checks before moving on to Ichorous or other games.

Current environment: preflight fails because LLVM, Rust, MinGW and other build
tools are absent. Outbound access is restricted and excludes multiple upstream
library/toolchain download hosts. **No Wine binary has been built or executed.**
GEX + Debian browser boot is verified; complete Wine integration remains pending.
