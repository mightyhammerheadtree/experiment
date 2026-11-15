# Upstream integration research

## GEX and Wine

- https://github.com/HeyPuter/gex — reusable browser x86/x64 translation, Linux ABI,
  host windows, graphics and process/filesystem APIs. Source research revision is
  recorded in `upstreams.lock.json`.
- npm `@gexemu/runtime@1.0.0` supplies compiled browser modules/kernels. npm
  `@gexemu/debian@1.0.0` supplies a slim Wasm Debian root. These exact artifacts
  booted successfully in Chromium through Windex. Package-lock records integrity.
- Neither package supplies Wine; no `@gexemu/wine` package was available when
  checked. The required Wine build must use GEX's Wasm ABI and a matching initialized
  win64 prefix, not a stock ELF build. See the architecture document for layout.
- The runtime npm metadata gitHead was not resolvable through GitHub. Installed
  npm artifacts and source research revisions must not be represented as identical.

## Existing emulator work

Bochs (https://bochs.sourceforge.io/) and existing x86 emulation projects informed
the reuse-first direction. Windex does not implement a new x86 CPU emulator or
claim universal static recompilation. GEX provides the runtime translation backend.
Qubes-style isolation is not required for this browser implementation.

## Linux references

- https://github.com/kilian-ai/linuxontab — optional v86 console, separate from
  the Windows backend; pinned source and assets are checked by deployment helpers.
- https://github.com/joelseverin/linux-wasm — study only, not integrated. See
  [the study](linux-wasm-research.md) for native Wasm Linux vs x86 translation.

## Intended game test

https://github.com/mightyhammerheadtree/ichorousport at
`141098993f0043ca676610883c2850470f22c165`, `raw/`:
`Ichorous.exe` is an x64 GameMaker PE with D3D11 and companion data/audio assets.
Import the complete raw game folder once Wine works. No successful Windows or
Ichorous execution is claimed yet.
