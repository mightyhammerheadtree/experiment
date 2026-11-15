# Browser runtime architecture

Windex is a browser application. `windex/web` contains its UI and runtime adapters;
`scripts/build-site.py`, `windex/staging.py`, and `windex/server.py` are internal
asset-deployment/hosting helpers, not a game-conversion CLI.

## Windows backend

`WindowsRuntime` loads same-origin GEX modules and constructs one `System` per
page lifecycle with `arch: x86` (GEX's shared x86/x64 backend). It mounts ordered
filesystem layers, configures host windows, Mesa graphics, gamepad/pointer input,
and boots the kernel. Audio is initialized from a user gesture. No network relay
or clipboard provider is installed.

Default deployment inputs are exact npm versions `@gexemu/runtime@1.0.0` and
`@gexemu/debian@1.0.0`. The Debian root contains Wasm Linux userspace, **not Wine**.
Real Chromium boot of this combination has passed. The npm runtime's metadata
source revision could not be resolved on GitHub; do not equate it with the separate
source research pin in `upstreams.lock.json`.

## Wine lifecycle

Boot → inspect Wine → `needs-wine` or `ready`. A user can install ordered trusted
`.tar`/`.tar.zst` layers after boot; filesystem additions are synchronized and
readiness is rechecked. The combined selection is limited to 1 GiB. Installation
is not transactional: after a partial failure, reload for a clean memory session.

Required default paths:

- `/wine/lib/wine/x86_64-unix/wine`: GEX-compatible bare Wasm or GEXWASM ELF64 envelope, not stock Linux Wine
- `/wine/lib/wine/x86_64-unix/wineserver`: matching Wasm wineserver
- `/wine/lib/wine/x86_64-windows/{ntdll,kernel32}.dll`
- `/pfx/{system,user}.reg`: initialized win64 prefix
- `/pfx/dosdevices/z:` → `/`; C: must resolve to a directory
- Optional `/wine/lib/wine/i386-windows/ntdll.dll` enables the x86/WoW64 gate

These are structural checks, not provenance, completeness, or execution proofs.
`Test Wine` separately spawns `cmd.exe /c ver` and requires a zero exit status.
A timeout terminates the foreground process and marks the session failed so the
user reloads instead of racing a potentially still-running process.

Game import validates relative paths and PE architecture, hashes the EXE for a
`/games/<sha256>` directory, copies companion files, and spawns Wine with a literal
argv and game working directory. No shell command interpolation is used. GEX
memory64 is selected for x64; WoW64 DLL availability gates x86. A successful Wine
test does not prove graphics, audio, anti-cheat, or game compatibility.

## Browser and hosting

Use a secure, cross-origin-isolated origin with WebGPU and Wasm threads.
Memory64 is required only by a configured memory64 build, not by every x64 EXE. OPFS is optional; memory-backed sessions are the default. Persistent
storage is origin-scoped and not a substitute for backing up original game files.
The development server binds 0.0.0.0 and sends COOP/COEP/CORP, MIME and range headers;
it accepts no uploads or execution requests. Browser WebAssembly isolation is not
a guarantee that arbitrary untrusted guest programs are harmless.

## Other Linux research

The optional linuxontab/v86 console uses its own Linux 4.16.13 i686 virtual PC and
9P file bridge. Its earlier Node boot/transfer smoke test is separate from GEX.
The joelseverin/linux-wasm project remains study-only; see its research document.

## Validation boundaries

Unit tests cover adapter contracts with mocks. Hosting tests cover deployment
assembly and HTTP behavior. `npm run test:browser` boots the actual npm runtime
in Chromium and expects Ready or Needs Wine, never a fabricated ready flag.
No compatible Wine bundle has yet been supplied or executed, and the intended
Ichorous `raw` x64 GameMaker/D3D11 test remains pending that prerequisite.

See [Wasm Wine build integration](wasm-wine-build.md) for the pinned build,
sanitized prefix packaging, layer manifest and pre-game validation gates.
