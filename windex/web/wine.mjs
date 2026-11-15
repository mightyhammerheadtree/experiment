// Check the actual mounted Wine installation, not merely a config enabled flag.
export const WINE64_LOADER = '/wine/lib/wine/x86_64-unix/wine';

export function memory64Supported() {
  // Minimal Wasm module defining an i64-indexed memory, with no executable code.
  return WebAssembly.validate(new Uint8Array([0,97,115,109,1,0,0,0,5,3,1,4,0]));
}

export function guestPath(path) {
  if (typeof path !== 'string' || !path.startsWith('/') || path.includes('\\') || /[\x00-\x1f]/.test(path) || path.split('/').slice(1).some(p => !p || p === '.' || p === '..')) throw Error('Expected an absolute guest path without traversal');
  return path;
}

// GEX's wcc64 emits an ELF64 envelope containing a Wasm module, not a stock ELF.
// Validate the mapped GEXWASM header and module bounds, not an arbitrary magic hit.
export function wineLoaderFormat(bytes) {
  const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  const wasm = (p, n) => n >= 8 && p >= 0 && p+n <= b.length && [0,97,115,109,1,0,0,0].every((v,i) => b[p+i] === v);
  if (wasm(0,b.length)) return 'wasm';
  const bad = () => { throw Error('Wine loader must be GEX-compatible WebAssembly or a GEXWASM ELF64 container, not stock Linux Wine'); };
  if (b.length < 64 || ![127,69,76,70,2,1,1].every((v,i)=>b[i]===v)) return bad();
  const v = new DataView(b.buffer,b.byteOffset,b.byteLength);
  const u64 = p => { const n = v.getBigUint64(p,true); if (n > BigInt(Number.MAX_SAFE_INTEGER)) return bad(); return Number(n); };
  if (v.getUint16(18,true) !== 62) return bad();
  const ph = u64(32), size = v.getUint16(54,true), count = v.getUint16(56,true);
  if (size !== 56 || count > 128 || ph+size*count > b.length) return bad();
  const loads = [];
  for (let i=0;i<count;i++) {
    const p=ph+i*size; if (v.getUint32(p,true)!==1) continue;
    const off=u64(p+8), va=u64(p+16), length=u64(p+32);
    if (off+length>b.length) return bad();
    loads.push({off,va,length});
  }
  for (const {off,length} of loads) {
    if (length<40 || ![71,69,88,87,65,83,77,0].every((n,i)=>b[off+i]===n)) continue;
    if (v.getUint32(off+8,true)!==1 || !(v.getUint32(off+36,true)&2)) return bad();
    const address=v.getUint32(off+12,true), n=v.getUint32(off+16,true);
    const segment=loads.find(s=>address>=s.va && address+n<=s.va+s.length);
    if (segment && wasm(segment.off+address-segment.va,n)) return 'gexwasm-elf64';
  }
  return bad();
}

export async function inspectWine(filesystem, config, report = () => {}) {
  const loader = guestPath(config.loader), prefix = guestPath(config.prefix);
  if (!loader.endsWith('/lib/wine/x86_64-unix/wine')) throw Error('This profile requires the GEX Wine64/WoW64 loader');
  const dist = loader.slice(0, -'/lib/wine/x86_64-unix/wine'.length);
  const checks = [];
  async function check(id, fn, required = true) {
    try {
      const detail = await fn(); const row = {id, status:'pass', detail}; checks.push(row); report(row); return true;
    } catch (cause) {
      const row = {id, status: required ? 'fail' : 'warning', detail:cause.message}; checks.push(row); report(row);
      if (required) { const error = new Error(`Wine readiness: ${cause.message}`); error.code = 'WINE_NOT_READY'; error.checks = checks; throw error; }
      return false;
    }
  }
  async function file(path) {
    let st;
    try { st = await filesystem.stat(path); } catch { throw Error('Missing guest file: ' + path); }
    if (st.type !== 'file') throw Error('Expected a regular guest file: ' + path);
    return path;
  }
  await check('wine-loader', async () => {
    await file(loader); const data = new Uint8Array(await filesystem.readFile(loader));
    return 'GEX Wine loader present (' + wineLoaderFormat(data) + ')';
  });
  await check('wine-server', async () => {
    await file(dist+'/lib/wine/x86_64-unix/wineserver');
    return 'Matching-distribution wineserver present';
  });
  await check('prefix-registry', async () => {
    await file(prefix+'/system.reg'); await file(prefix+'/user.reg');
    const registry = await filesystem.readFile(prefix+'/system.reg', {encoding:'utf-8'});
    if (!/^#arch=win64\s*$/m.test(registry)) throw Error('Wine prefix is not initialized as win64; an empty folder or win32 prefix is insufficient');
    return 'Initialized win64 registry present';
  });
  await check('wine-dlls', async () => {
    await file(dist+'/lib/wine/x86_64-windows/ntdll.dll'); await file(dist+'/lib/wine/x86_64-windows/kernel32.dll');
    return '64-bit Wine core DLLs present';
  });
  await check('drive-z', async () => {
    const target = await filesystem.readlink(prefix+'/dosdevices/z:');
    if (target !== '/') throw Error('Wine Z: drive must map to guest / so browser-imported files can be launched');
    return 'Z: maps to the guest filesystem root';
  });
  await check('drive-c', async () => {
    const st = await filesystem.stat(prefix+'/dosdevices/c:', {follow:true});
    if (st.type !== 'directory') throw Error('Wine C: mapping does not resolve to a directory');
    return 'C: drive resolves';
  });
  const wow64 = await check('wow64', async () => {
    await file(dist+'/lib/wine/i386-windows/ntdll.dll');
    return 'WoW64 DLLs present; x86 game execution still requires a successful runtime test';
  }, false);
  return {loader, prefix, wow64, checks, status:'files-ready-not-execution-verified'};
}
