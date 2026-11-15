# Windex

**An in-browser runtime for x86 and x64 Windows games using GEX, a Wasm Linux environment, and Wasm Wine.**

Windex imports a local game folder and runs its EXE through one reusable runtime.
It is not a CLI product, a per-game converter, or a static-recompilation pipeline.
The old Glassforge implementation has been removed.

## Current status

- Real published **GEX 1.0.0 + Wasm Debian 1.0.0** assets are assembled into the browser deployment.
- **Real Chromium integration check passed:** cross-origin isolation, GEX modules, kernel boot and filesystem mount; the application correctly enters **Needs Wine**.
- Browser controls install trusted local Wine tar layers, check the Wasm loader/prefix/DLLs/drive mappings, and test `cmd.exe /c ver` with a timeout.
- Local folder/EXE import preserves companion assets and launches via the GEX process API. x86 requires WoW64; the x64 profile requires Wasm memory64.
- **Missing:** a compatible built Wasm Wine distribution and initialized prefix. They are not included in the npm Debian base. Windows execution and Ichorous gameplay remain unverified.

## Use the browser app

Deployment developers need Node 22+ and Python 3.10+:

```sh
npm ci
npm run build
npm run dev
```

Open the live preview or http://localhost:8080. These are development/hosting
commands; all game import and runtime interaction happens in the browser.
There is no upload or server-side game-execution endpoint.

1. Start the environment. Without Wine, it reports exactly which file is missing.
2. Choose **Install Wine** and select trusted GEX-compatible `.tar`/`.tar.zst` layers containing the Wine distribution and prefix.
3. Use **Test Wine** to verify actual process execution, not merely file presence.
4. Import the entire game folder, choose its EXE, and run it.

A stock Linux Wine package or a Windows Wine installer will **not** work. Windex
requires the GEX Wasm Wine build. Runtime bundles execute code inside the guest;
only install bundles you trust. Memory-only sessions lose installed layers on reload.

Optional deployment configuration: copy `windex.build.example.json` to
`windex.build.local.json` and supply your local runtime/tree paths before building.
Serve the generated `work/site` with COOP `same-origin`, COEP `require-corp`, Wasm
MIME types, and byte-range support. HTTPS is required outside localhost.

## Tests

```sh
npm test                 # adapter and browser file-handling unit tests
npm run test:hosting     # static-hosting and deployment assembly tests
npm run test:browser     # real headless Chromium; run dev server first
```

The browser smoke test checks kernel boot, not Wine or game compatibility. Its
software WebGPU is a test facility, not a gameplay performance measurement.

## Architecture and licensing

`Game folder → Wine Windows APIs → GEX x86/x64 translation + Linux ABI → Wasm/WebGPU`

The optional linuxontab/v86 console is a separate 32-bit Linux VM, not the Windows
backend. linux-wasm was [studied only](docs/linux-wasm-research.md); its kernel is
not substituted into GEX.

See [architecture](docs/windex-architecture.md), [upstream research](docs/upstream-research.md),
and `upstreams.lock.json`. GEX's AGPL obligations, Wine's LGPL obligations, and
Debian's per-package licenses apply to redistributed components. Preserve upstream
notices and supply corresponding source as required. Installed npm runtime packages
carry their own LICENSE/NOTICE/THIRD-PARTY material, copied into deployment assets.
