# Reuse-first technical decision log

Reviewed 2026-11-15 using upstream GitHub repositories and READMEs.
The SourceForge site cannot be accessed from this workspace's network allowlist;
Bochs was reviewed through its official GitHub repository instead.

| Project | Relevant capability | Decision |
| --- | --- | --- |
| [GEX](https://github.com/HeyPuter/gex) | x86/i386 and x64 translation to Wasm, Wine integration, recording and AOT eject | Primary backend; wrap upstream tools instead of writing a CPU translator. Audited revision: `9004980758dbba3f16fa40db7dbc69cc4a9a2eb9`. Correction after source inspection: despite 32-bit-only comments, wine32.rs also implements **wine64** projects, memory64 and NT64 trampolines. eject-site consumes the shared launch manifest. Actual x64 end-to-end export still needs validation; see x64-integration.md. |
| [Bochs](https://github.com/bochs-emu/Bochs) | Portable full-system IA-32/x86-64 CPU, devices and BIOS emulation; accuracy-first | Reference for instruction behavior and possible differential tests, not an EXE-to-static-Wasm compiler. Do not embed a full PC/Windows image as if it were a static recompilation. |
| [v86](https://github.com/copy/v86) | Browser PC emulator, runtime x86-to-Wasm translation | Possible separately labelled emulation fallback, not static recompilation. README explicitly lists 64-bit extensions as missing. Not implemented here. |
| [Box64](https://github.com/ptitSeb/box64) | Linux userspace x86-64 execution on non-x86 hosts with native library bridges and dynarec | Useful architecture/reference; not an existing browser AOT backend. |
| [Remill](https://github.com/lifting-bits/remill) | x86/amd64 instruction semantics lifted into LLVM bitcode | Consider if GEX has a specific semantics gap; does not provide Windows APIs, game assets, browser graphics or a complete port by itself. |
| [McSema](https://github.com/lifting-bits/mcsema) | Binary lifting framework using LLVM | Candidate for a future research pipeline, not a drop-in game-to-browser converter. |
| [iced](https://github.com/icedland/iced) | Existing x86/x64 decoding and disassembly library | Prefer an established decoder if instruction-level inspection is added. Current code only reads PE metadata and contains no instruction decoder. |
| [retrowin32](https://github.com/evmar/retrowin32) | Windows emulation project | Further compatibility/API review required before proposing an adapter; not integrated. |
| [Qubes core-admin](https://github.com/QubesOS/qubes-core-admin) | Qubes VM administration | Optional operator isolation environment, not instruction lifting. Do not copy OS administration code into the translator. |

## Licensing boundary

No upstream emulator/translator source has been copied into this tool. GEX is
AGPL-3.0-only; Bochs is reported by GitHub as LGPL-2.1; other dependencies retain
their own licenses. Before distributing runtime Wasm, Wine, bundled libraries,
or game assets, review the actual licenses/NOTICE files, supply corresponding
source and notices as required, and obtain permission to distribute game data.
Executing an external tool does not remove obligations attached to its output's
bundled runtime components. These notes are not legal advice.

## Implementation rule

Before implementing decoding, lifting, CPU flags, x87/SSE, PE relocation,
Windows APIs, graphics translation or sound: search upstream implementations,
identify the exact missing capability, assess license compatibility, and prefer
an upstream fix or adapter. Do not equate an instruction lifter with a complete
Windows game runtime. Never label a JIT/emulation fallback as a static build.
