# Studying joelseverin/linux-wasm for Windex

Reviewed 2026-11-15 at commit
`3103d5c877a8f6251b4b451c866a46941fd1fab3`.

The supplied site is https://joelseverin.github.io/linux-wasm/ . This sandbox
cannot fetch that GitHub Pages host directly under its network policy. Research
used the corresponding [source repository](https://github.com/joelseverin/linux-wasm),
its README, LICENSE, build script and runtime source. No claim is made that its
live demo or kernel build has been run here.

## Three different meanings of “Linux in a browser”

| Project | What executes | What provides Linux behavior | x64 Windows implications |
| --- | --- | --- | --- |
| linuxontab/v86 | x86 machine code translated/emulated in Wasm | A real **x86** Linux kernel in a virtual PC | Current v86 has no x86-64 guest execution; not the primary x64 route |
| joelseverin/linux-wasm | Kernel and compatible userspace compiled **to Wasm** | A real Linux kernel ported to the Wasm architecture | wasm64 means 64-bit Wasm pointers, **not** x86-64 CPU emulation |
| GEX | wasm32 programs plus translated x86/x64 machine code | GEX's own kernel/Linux ABI implementation | Already has the translation, Wasm Wine integration and browser graphics route we need |

These are not interchangeable memory images or kernels. Booting a kernel does
not supply Windows APIs, decode x86 instructions, or make arbitrary PE files into
native Wasm executables.

## Upstream findings

- The README describes a 7.0-era kernel port, with wasm32_nommu and
  wasm64_nommu build variants. It describes 64-bit userspace as experimental.
  These are upstream claims, not independently reproduced test results.
- The documented stack uses modified LLVM **18.1.2**, a compiler wrapper,
  patched musl **1.2.5**, BusyBox **1.36.1**, an initramfs and custom browser glue.
  It is not GEX's LLVM 22 / Wine toolchain.
- The README lists MMU support, ELF support, additional drivers and a better
  runtime as future work. Existing x86 ELF executables must not be assumed to run.
- `runtime/linux.js` creates shared Wasm memory and task/Worker coordination.
- `runtime/linux-worker.js` imports host callbacks and instantiates the kernel;
  `wasm_load_executable` compiles the selected userspace executable as a
  WebAssembly module. It manages signals, stacks, TLS and context/exec changes.
  This is not an x86 decoder or a Windows PE loader.
- The supplied server sends COOP/COEP, reflecting its shared-memory/Atomics
  requirements. Those headers fit Windex hosting, but do not imply ABI identity.
- `linux-wasm.sh` fetches kernel/compiler branches as well as musl and BusyBox
  from hosts outside this sandbox's network allowlist. Reproducing a build would
  also require resolving exact dependency commits, not just pinning the script.
- LICENSE explicitly says **GPL-2.0-only** for originating repository code;
  patches use their target project's license. GitHub's `NOASSERTION` metadata is
  not evidence that no license exists.

## What is useful to study/reuse

1. Real Linux task lifecycle and syscall behavior as a reference for validating
   our chosen Linux ABI path.
2. The Wasm userspace/kernel boundary, exec/signal/TLS handling and shared-memory
   restrictions, before proposing a syscall bridge.
3. Toolchain constraints and NOMMU implications for Wine's virtual address needs.
4. Browser host integration and debugging techniques, with proper license review
   before copying code. No runtime code from this project is copied into Windex.

## Could GEX use this real kernel instead of its own?

Potentially a research project, not a present capability or simple adapter. We
would first need to define and prove:

- A backend boundary for GEX's translated code/syscalls rather than GEX's current
  kernel memory/layout contract. Calls cannot simply be pointed at kernel JS.
- Address-space and pointer translation, memory64/compact-address behavior,
  mapping/protection, shared memory, Wine reservations, signals, threads and TLS.
- An executable/binfmt path for translated ELF and PE/Wine processes, with
  process lifecycle synchronization across the two systems.
- File descriptor/filesystem ownership, dynamic linking, futex/Atomics behavior,
  graphics/Wayland/D3D, audio and browser event scheduling.
- A reproducible matching build and test suite, followed by actual Windows game
  tests. Sharing a JS ArrayBuffer alone does not solve these contracts.

Combining source from GPL-2.0-only, AGPL-3.0-only and other projects also requires
careful boundary/license review; do not assume copying code into one executable
is automatically permitted. Separate programs and standard interfaces differ
from merging implementations. This is not a legal compatibility determination.

## Decision for Windex now

Keep **GEX + its pinned Wasm Wine as the primary direct-EXE runtime**; use the
linuxontab/v86 stack as a separate optional real-Linux console with explicit file
transfers. Record linux-wasm as a pinned research reference, **not** a third
working backend. Do not let native-kernel integration block an already available
runtime-translation path, and do not describe the current design as one shared
real Linux kernel.
