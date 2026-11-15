# Windex

**A reusable browser workspace for Windows games, plus a real Linux console.**

Windex assembles **GEX + its Wasm Wine runtime** for direct EXE execution and the
**linuxontab/v86 stack** for an optional Linux VM. Import an EXE and companion
files into the browser; no per-game AOT project is required by the new launcher.
This is **runtime translation/emulation**, not universal static recompilation.

> **Current status:** browser shell, GEX public-API adapter, local file imports,
> runtime asset staging and optional Linux console are implemented. A real
> v86/Linux guest boot and 9P file transfer passed in Node. **Windows execution
> remains unverified**: the compiled GEX runtime/Wine filesystem tree is not
> supplied or built in this sandbox. An unstaged backend is visibly disabled.
> No claim is made that arbitrary games—or Ichorous—already work.

## Architecture, without a hidden kernel swap

```
Game folder → Wasm Wine64/WoW64 → GEX x86/x64 translation + Linux ABI → Wasm/WebGPU
Linux ISO   → v86 virtual x86 PC → real 32-bit Linux kernel → console + 9P
```

These are separate backends inside one application, not two interchangeable
kernels. v86 currently lacks x64 guests. GEX already provides its own Linux
kernel/syscall layer. [joelseverin/linux-wasm](docs/linux-wasm-research.md), a real
Linux kernel compiled to Wasm, is being studied but is **not integrated**.

## Try the shell

Python 3.10+; the Windex static server/stager need only the standard library:

```sh
python3 -m windex serve
```

Open http://localhost:8080 locally or use your environment's preview. Without
assets, the interface explains what is missing rather than faking execution.

For a working Linux console backend, stage a pinned linuxontab checkout:

```sh
python3 -m windex stage --linuxontab /path/to/linuxontab -o work/windex-linux
python3 -m windex serve --site work/windex-linux
```

See [Windex architecture and deployment](docs/windex-architecture.md) for the
exact source revision, LFS handling, memory requirements and licensing caveats.

## Add the Windows runtime once

On a machine capable of building GEX/Wine, build GEX's general runtime package
and prepare its compatible Linux + Wasm Wine64/WoW64 filesystem/prefix trees:

```sh
python3 -m windex stage -o work/windex \
  --linuxontab /path/to/linuxontab --runtime /path/to/built-gex-runtime \
  --tree /path/to/linux-base.tar --tree /path/to/wine-prefix.tar
python3 -m windex serve --site work/windex
```

This is asset staging, not an automatic compiler/toolchain installer. Preparing
the guest trees remains an open integration task. A stock Linux ISO or Wine
installation cannot simply replace the GEX-compatible trees.

Then the browser launcher:
- Imports a folder locally, preserves asset paths and lets you select an EXE.
- Boots one GEX session; starts the configured Wasm Wine loader with that EXE.
- Uses on-demand translation/cache, graphics, audio and gamepad adapters.
- Supports an opt-in persistent OPFS filesystem; otherwise session memory only.
- Never posts game files to the hosting server. Network relays/clipboard access
  are not configured. Optional Linux transfers are explicit and separate.

Full browser isolation/WebGPU/memory64 support and Wine compatibility still
apply. This does not bypass DRM, anti-cheat, missing Windows APIs or game-specific
requirements, and browser sandboxing is not a malware-security guarantee.

## Developer tools retained

The older Glassforge `python -m forge ...` CLI and UI remain available for PE
inspection, bounded iced-x86 code discovery, upstream setup/probing, preflight,
and optional per-game AOT exports. They are not the Windex runtime launch path.
Install their dependencies with `pip install -r requirements.txt` in a venv.

- [Windex architecture, staging, validation and limitations](docs/windex-architecture.md)
- [Native-Wasm Linux research](docs/linux-wasm-research.md)
- [Upstream source pins and roles](upstreams.lock.json)
- [Legacy GEX builder/probe helpers](docs/builder.md)
- [Legacy static-port workflow](docs/workflow.md)
- [Earlier x64 source findings](docs/x64-integration.md)
- [Ichorous metadata analysis](docs/sample-analysis.json)

## Tests

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
node --test tests/js/*.test.mjs  # Node 22+

# Optional REAL v86/Linux boot + 9P test, after staging linux4.iso:
node scripts/smoke-linux.cjs work/windex-linux/assets/linux
```

GEX adapter tests use mocked upstream classes; the optional Linux smoke test
uses real artifacts. Neither proves Wine/Windows gameplay compatibility.
No upstream binary blobs or games are committed. Review all runtime/BIOS/Linux,
AGPL/GPL, corresponding-source and game redistribution obligations before
publishing staged assets; copying code from multiple repos does not waive them.
