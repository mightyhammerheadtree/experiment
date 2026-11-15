# Windex: universal browser runtime, not per-game static ports

## Product shift

The primary experience is now **import game folder → run EXE in a reusable
browser session**. It does not require recording each game or producing an AOT
project. Runtime translation/JIT is intentional; cached translations are an
optimization, not a static-recompilation claim. Legacy `forge` commands remain
available as developer/optional AOT tools, not the main application.

This is one integration superproject, not a source-code merger or a claim to
have rewritten Wine/Linux. Upstream code and compiled artifacts retain their
own license/build boundaries. No new GitHub repository has been created.

## Why two execution backends?

```
                         Windex browser UI
                      /                      \
       GEX public System API                v86 API
       ├─ Wasm Wine64/WoW64                  ├─ virtual x86 PC
       ├─ runtime x86/x64 translation        ├─ BIOS + Linux ISO
       ├─ GEX Linux syscall/kernel layer    ├─ real 32-bit Linux kernel
       ├─ guest FS / optional OPFS           └─ separate 9P filesystem
       └─ graphics, audio, input
```

[linuxontab](https://github.com/kilian-ai/linuxontab) uses v86; current v86 does
not execute x86-64 guests. GEX's translated-code/runtime API is built around its
own Linux ABI/memory contract. Running GEX under v86 is neither necessary nor a
working way to “share” that real kernel. Windex therefore keeps a separate
optional real-Linux console and explicitly labels the primary Windows engine.

[joelseverin/linux-wasm](linux-wasm-research.md) is a different native-Wasm Linux
kernel project. It is a useful research reference, **not integrated**. A future
single-real-kernel backend would need serious syscall/address-space/loader and
device work. wasm64 is not an x64 CPU emulator.

## Implemented runtime integration

- Game folder/file imports stay entirely in the browser. No upload endpoint in
  the Windex hosting server. Relative paths and case-insensitive duplicates are
  checked; a lightweight browser-side PE header check recognizes x64/x86.
- GEX package modules are loaded from the site's own origin through their real
  public entry points. One `System({arch:'x86', xcache:true})` per page.
- Filesystem trees are laid in the guest before boot. The optional OPFS store
  persists writes; otherwise memory/session only. Root `/games/SHA256-OF-EXE`
  is stable across launches of the same EXE. Imported source files are rewritten
  on launch; other guest save files may remain. Changing a binary changes that
  root, and Wine/game-specific save behavior still needs validation.
- Run imports the folder into guest FS and `spawn`s the configured Wasm Wine
  loader with a single Windows `Z:\games\...\program.exe` argument and its
  correct guest working directory. No shell interpolation or build step.
- x64 launch requests `GEX_MEM64=1`; x86 relies on a compatible WoW64-enabled
  Wine64 tree (`WINEGEX_WOW64=1` in the default staged profile). memory64 browser
  support and the prepared runtime artifacts remain real requirements.
- HostWindows displays guest canvases; MesaGl enables the D3D device; WebAudio
  is created in the Run gesture; GEX Gamepads/PointerLock are attached. Window
  management is a basic prototype, not a complete desktop/window manager.
- Both stdout/stderr streams are drained. The foreground process can be stopped;
  Wine services may remain for the session. Only one foreground launch is
  allowed by the UI; the GEX system may have multiple internal Wine processes.
- Linux uses v86 assets sourced locally from a clean pinned linuxontab checkout,
  not linuxontab's website/social/tunneling UI. Serial and VGA output are shown;
  explicit one-file transfers use v86's independent 9P API. The ISO must mount
  the share (linux4.iso normally mounts it at `/mnt`). This is not a shared GEX
  filesystem, a syscall bridge or shared guest memory. There is no automatic
  transfer of running guest processes between engines.
- No Wisp/network relay, clipboard integration, third-party services or game
  download is enabled by the Windex adapters. Guest/browser sandboxing is not a
  malware security guarantee. Large games can exhaust tab/device memory.

## Preparing an actual deployment

Linux console only (available without building GEX):

```sh
git clone https://github.com/kilian-ai/linuxontab /build/linuxontab
# Fetch actual LFS blobs if this checkout contains pointers.
git -C /build/linuxontab checkout 08eb427e5b926463e2fd8f24bba06287c06fe4ba
python -m windex stage --linuxontab /build/linuxontab -o work/windex-linux
python -m windex serve --site work/windex-linux
```

A minimal default UI without assets is also available with
`python -m windex serve`; unavailable backends are disabled rather than simulated.

Windows runtime + Linux (on a provisioned build machine):

1. Build the GEX revision in upstreams.lock.json with its matching tools,
   Wine64/WoW64, x86 and memory64 browser hosts, graphics and other required
   dependencies. Existing `forge setup` helpers may assist; see builder.md.
2. Build GEX's general runtime package, **not an ejected game's app.mjs**:
   `make -C /build/gex runtime PKG=/build/windex-runtime`.
3. Prepare GEX-compatible guest filesystem trees containing Linux userland,
   GEX's **patched Wasm Wine** distribution at `/wine`, an initialized prefix
   at `/pfx` with the correct browser display/audio settings, dependencies and
   required native Wasm DLLs. Include upstream-provided marks/xattrs as needed.
   A stock distro Wine binary, a v86 ISO, and an arbitrary tar are not substitutes.
   This tree build is **still manual/unvalidated**, not secretly supplied here.
4. Stage the runtime once, then reuse it for many game imports:

```sh
python -m windex stage -o /build/windex-site \
  --linuxontab /build/linuxontab --runtime /build/windex-runtime \
  --tree /build/linux-base.tar --tree /build/wine-prefix.tar
python -m windex serve --site /build/windex-site --host 0.0.0.0 --port 8080
```

All tree layers are laid at `/`, in order. Edit the generated windex.json if
loader/prefix paths differ. Bump the OPFS store name when changing incompatible
root filesystem versions. Persistent mode is opt-in; it retains game/prefix
files on the hosting origin. Clear origin storage to reset it (backup saves
first). Files are selected locally again on reload; there is no persistent host
File System Access permission or game-library metadata database yet.

Stage refuses an existing output directory, source/output recursion, symlinked
runtime packages, missing modules and LFS pointers. It hashes staged artifacts.
These hashes record bytes, **not** a signature or proof that an operator-supplied
runtime was built from the expected source revision. provenance.json makes that
lack of build attestation explicit. Do not publish runtime/game assets without
license review; linuxontab has no top-level license for all its modifications.
GEX's build normally emits LICENSE/NOTICE/THIRD-PARTY alongside its runtime;
retain them and meet corresponding-source obligations when distributing.

Hosting must support same-origin assets, correct .wasm/.mjs MIME types, byte
ranges, HTTPS/localhost secure context and COOP/COEP isolation. The Python
server provides headers/ranges for development but is not hardened public
hosting. Generated `_headers` is a convenience for hosts supporting that format.
Embedding in an outer preview frame may restrict isolation/WebGPU; a standalone
secure tab may be needed even when the HTTP headers are correct.

## What has actually been tested?

- Python tests cover staging/provenance, configuration, missing artifacts,
  symlink/traversal rejection, range responses and isolation headers.
- Node tests cover browser file handling and GEX adapter orchestration with
  **mocked GEX classes**. They do not establish actual Wine or graphics support.
- An actual **v86 Wasm + Linux 4.16.13 i686** session booted in Node, answered
  `uname -a`, and read a host-supplied file over 9P. Reproduce with
  `node scripts/smoke-linux.cjs work/windex-linux/assets/linux` after staging.
  This is not a browser screenshot/rendering test; it uses the same emulator
  core/BIOS/ISO with a Node host.
- This sandbox has no installed browser for visual/WebGPU tests. No real GEX
  runtime package/Wine tree was built, no Windows EXE was launched through
  Windex here, and Ichorous gameplay remains unverified.
