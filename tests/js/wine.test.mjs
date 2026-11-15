import test from 'node:test';
import assert from 'node:assert/strict';
import {guestPath, inspectWine} from '../../windex/web/wine.mjs';
const config = {loader:'/wine/lib/wine/x86_64-unix/wine', prefix:'/pfx'};
function fs({elf=false, registry='#arch=win64\n', z='/', wow64=true}={}) {
  return {
    async stat(path) { if (!wow64 && path.includes('/i386-windows/')) throw Error('ENOENT'); return {type:path.endsWith('/c:')?'directory':'file'}; },
    async readFile(path, options) { return options ? registry : new Uint8Array(elf?[127,69,76,70,0,0,0,0]:[0,97,115,109,1,0,0,0]); },
    async readlink() { return z; }
  };
}
test('guest configuration rejects traversal and ambiguous absolute paths', () => {
  for (const p of ['relative','/a/../b','/a//b','/a/','/a\\b','/a\0b']) assert.throws(()=>guestPath(p));
});
test('stock ELF Wine is explicitly rejected', async () => {
  await assert.rejects(inspectWine(fs({elf:true}),config),/WebAssembly/);
});
test('uninitialized or win32 prefixes rejected', async () => {
  for (const registry of ['', '#arch=win32\n']) await assert.rejects(inspectWine(fs({registry}),config),/win64/);
});
test('wrong Z drive prevents launching browser imports', async () => {
  await assert.rejects(inspectWine(fs({z:'/other'}),config),/Z: drive/);
});
test('missing WoW64 is a warning, never a false x86-ready result', async () => {
  const result = await inspectWine(fs({wow64:false}),config);
  assert.equal(result.wow64,false); assert.equal(result.checks.at(-1).status,'warning');
  assert.equal(result.status,'files-ready-not-execution-verified');
});

test('GEX ELF64 envelope accepted, stock and corrupt ELF rejected', async () => {
  const {wineLoaderFormat} = await import('../../windex/web/wine.mjs');
  const b = new Uint8Array(512), v = new DataView(b.buffer);
  b.set([127,69,76,70,2,1,1]); v.setUint16(18,62,true); v.setBigUint64(32,64n,true); v.setUint16(54,56,true); v.setUint16(56,2,true);
  for (const [p,off,va,len] of [[64,0,4096,256],[120,256,4352,256]]) {
    v.setUint32(p,1,true); v.setBigUint64(p+8,BigInt(off),true); v.setBigUint64(p+16,BigInt(va),true); v.setBigUint64(p+32,BigInt(len),true);
  }
  b.set([0,97,115,109,1,0,0,0],192); b.set([71,69,88,87,65,83,77,0],256);
  v.setUint32(264,1,true); v.setUint32(268,4288,true); v.setUint32(272,8,true); v.setUint32(292,2,true);
  assert.equal(wineLoaderFormat(b),'gexwasm-elf64');
  v.setUint32(272,4096,true); assert.throws(()=>wineLoaderFormat(b),/GEXWASM/);
  b.fill(0,256,264); assert.throws(()=>wineLoaderFormat(b),/GEXWASM/);
});
