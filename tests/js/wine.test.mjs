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
