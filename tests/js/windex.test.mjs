import test from 'node:test';
import assert from 'node:assert/strict';
import {collectFiles, peArchitecture, relativePath, localURL} from '../../windex/web/files.mjs';
import {WindowsRuntime} from '../../windex/web/runtime.mjs';
import {LinuxConsole} from '../../windex/web/linux.mjs';

function exe(name = 'game.exe', machine = 34404) {
  const bytes = new Uint8Array(128), view = new DataView(bytes.buffer);
  view.setUint16(0, 0x5a4d, true); view.setUint32(0x3c, 64, true); view.setUint32(64, 0x4550, true); view.setUint16(68, machine, true);
  return new File([bytes], name);
}
test('safe paths preserve game asset subfolders', () => assert.equal(relativePath('assets/level 1.dat'), 'assets/level 1.dat'));
test('unsafe file paths rejected', () => { for (const p of ['../x','/x','a//b','a\\b','a/./b','C:x','a\0b']) assert.throws(() => relativePath(p)); });
test('case-insensitive duplicates rejected', () => assert.throws(() => collectFiles([exe('game.exe'),exe('GAME.exe')]), /duplicate/));
test('folder imports strip only the shared top-level folder', () => {
  const a = exe(); Object.defineProperty(a, 'webkitRelativePath', {value: 'Game/bin/game.exe'});
  assert.equal(collectFiles([a], {folder: true})[0].path, 'bin/game.exe');
});
test('import byte limit enforced before reading data', () => assert.throws(() => collectFiles([exe()], {limit: 10}), /limit/));
test('PE metadata identifies x64 and x86 in browser', async () => { assert.equal(await peArchitecture(exe()),'x64'); assert.equal(await peArchitecture(exe('a.exe',332)),'x86'); });
test('bad PE or unsupported CPU rejected', async () => { await assert.rejects(peArchitecture(new File(['bad'],'a.exe'))); await assert.rejects(peArchitecture(exe('arm.exe',43620))); });
test('remote runtime modules rejected', () => assert.throws(() => localURL('https://elsewhere.invalid/a','https://windex.invalid/'), /same-origin/));

function runtimeFixture({wine = true, wow64 = true} = {}) {
  const calls = [], logs = []; let finish;
  class System extends EventTarget {
    constructor(options) { super(); calls.push(['system',options]); }
    async boot() { calls.push(['boot']); }
    async sync() { calls.push(['sync']); }
    spawn(argv, opts) { calls.push(['spawn',argv,opts]); return {started: Promise.resolve(12), exited: new Promise(r => finish = r), stdout: new ReadableStream({start(c) { c.enqueue(new TextEncoder().encode('program output')); c.close(); }}), stderr: new ReadableStream({start(c) { c.close(); }}), kill(signal) { calls.push(['kill',signal]); finish({code:143}); }}; }
    async shutdown() { calls.push(['shutdown']); }
  }
  class FS { constructor() {}
    async stat(path) {
      if (!wine || (!wow64 && path.includes('/i386-windows/'))) throw Error('ENOENT');
      return {type: path.endsWith('/c:') ? 'directory' : 'file'};
    }
    async readFile(path, options) { return options?.encoding ? 'WINE REGISTRY Version 2\n#arch=win64\n' : new Uint8Array([0,97,115,109,1,0,0,0]); }
    async readlink() { return '/'; }
    addTar(url) { calls.push(['tar',url]); } async mkdir(path) { calls.push(['mkdir',path]); } async writeFile(path,data) { calls.push(['file',path,data.length]); } }
  class HostWindows extends EventTarget { constructor() { super(); this.env = {WAYLAND_DISPLAY: 'wayland-0'}; } }
  class Audio { constructor() { this.ready = Promise.resolve(); calls.push(['audio']); } }
  const modules = {'index':{System},'fs':{MemoryFilesystem:FS,OPFSFilesystem:FS},'windows-host':{HostWindows},'gl':{MesaGl:class {}},'audio':{WebAudio:Audio},'input':{Gamepads:class {},PointerLock:class {}}};
  const config = {enabled:true,package:'/assets/gex/',trees:['/assets/trees/base.tar'],loader:'/wine/lib/wine/x86_64-unix/wine',prefix:'/pfx',store:'test',env:{WINEGEX_WOW64:'1'},d3d:true};
  const runtime = new WindowsRuntime(config,{platform:{isolated:true,gpu:true,opfs:true},load:async url => { calls.push(['module',url]); return modules[new URL(url).pathname.split('/').pop().slice(0,-4)]; }});
  runtime.addEventListener('log', e => logs.push(e.detail));
  return {runtime,calls,logs,finish: code => finish(code)};
}
test('GEX boot uses public System API with runtime translation, no per-game build', async () => {
  const {runtime,calls} = runtimeFixture(); await runtime.boot(); assert.equal(runtime.state,'ready');
  assert.deepEqual(calls.find(c=>c[0]==='system')[1],{arch:'x86',xcache:true});
  assert.equal(calls.filter(c=>c[0]==='tar').length,1);
  assert.equal(runtime.system.network,undefined);
});
test('EXE and companion files go straight to guest FS then Wine spawn', async () => {
  const {runtime,calls,finish,logs} = runtimeFixture(); await runtime.boot();
  const entries = collectFiles([exe('hello ; literal.exe'),new File(['asset'],'data.win')]);
  await runtime.launch(entries,'hello ; literal.exe'); assert.equal(runtime.state,'running');
  assert.equal(calls.filter(c=>c[0]==='file').length,2);
  const [,argv,opts] = calls.find(c=>c[0]==='spawn');
  assert.equal(argv[0],'/wine/lib/wine/x86_64-unix/wine'); assert.equal(argv.length,2);
  assert.match(argv[1],/^Z:\\games\\[0-9a-f]{64}\\hello ; literal.exe$/);
  assert.equal(opts.env.WINEPREFIX,'/pfx'); assert.equal(opts.env.WINEGEX_WOW64,'1'); assert.equal(opts.env.GEX_MEM64,'0'); assert.equal(opts.env.WINEGEX_DOOR,'1'); assert.equal(opts.env.WINEGEX_NO_REGSAVE,'1');
  finish({code:0}); await new Promise(r=>setTimeout(r,0)); assert.equal(runtime.state,'ready');
  assert.ok(logs.includes('program output'));
});
test('one System per page lifecycle is enforced', async () => { const {runtime} = runtimeFixture(); await runtime.boot(); await assert.rejects(runtime.boot(),/One GEX/); });
test('unconfigured Windows runtime does not pretend to run a game', async () => { const r = new WindowsRuntime({enabled:false}); await assert.rejects(r.boot(),/not been staged/); });
test('non-isolated environment rejected before loading any modules', async () => { const {runtime,calls} = runtimeFixture(); runtime.platform.isolated = false; await assert.rejects(runtime.boot(),/isolation/); assert.equal(calls.length,0); });
test('unsupported persistence rejected explicitly', async () => { const {runtime} = runtimeFixture(); runtime.platform.opfs = false; await assert.rejects(runtime.boot({persistent:true}),/storage/); });
test('invalid selected EXE resets state without spawning', async () => { const {runtime,calls} = runtimeFixture(); await runtime.boot(); await assert.rejects(runtime.launch(collectFiles([new File(['bad'],'a.exe')]),'a.exe')); assert.equal(runtime.state,'ready'); assert.equal(calls.filter(c=>c[0]==='spawn').length,0); });
test('concurrent EXE launches rejected', async () => { const {runtime} = runtimeFixture(); await runtime.boot(); const entries=collectFiles([exe()]); await runtime.launch(entries,'game.exe'); await assert.rejects(runtime.launch(entries,'game.exe'),/one foreground/); });
test('Linux VM is independently gated when not staged', async () => { const linux=new LinuxConsole({enabled:false}); await assert.rejects(linux.boot(null),/Stage linuxontab/); assert.equal(linux.emulator,null); });

test('base Linux without Wine boots but cannot launch an EXE', async () => {
  const {runtime,calls} = runtimeFixture({wine:false}); await runtime.boot();
  assert.equal(runtime.state,'needs-wine');
  await assert.rejects(runtime.launch(collectFiles([exe()]),'game.exe'),/Boot Windows/);
  assert.equal(calls.filter(c=>c[0]==='spawn').length,0);
});
test('Wine installation rejects non-archive layers', async () => {
  const {runtime} = runtimeFixture({wine:false}); await runtime.boot();
  await assert.rejects(runtime.installWine([new File(['x'],'wine.exe')]),/runtime layers/);
  assert.equal(runtime.state,'needs-wine');
});
test('Wine execution test waits for actual process exit', async () => {
  const {runtime,calls,finish} = runtimeFixture(); await runtime.boot();
  const result = runtime.testWine(); assert.equal(runtime.state,'testing-wine');
  assert.deepEqual(calls.find(c=>c[0]==='spawn')[1].slice(1),['cmd.exe','/c','ver']);
  finish({code:0}); assert.equal((await result).status,'passed'); assert.equal(runtime.state,'ready');
});
test('Wine execution failure does not report success', async () => {
  const {runtime,finish} = runtimeFixture(); await runtime.boot();
  const result = runtime.testWine(); finish({code:1});
  await assert.rejects(result,/exit code 1/); assert.equal(runtime.wineTest.status,'failed');
});
test('Wine execution timeout requires session reload', async () => {
  const {runtime} = runtimeFixture(); await runtime.boot();
  await assert.rejects(runtime.testWine({timeoutMs:5}),/timed out/); assert.equal(runtime.state,'failed');
});
test('x86 launch is gated on installed WoW64 DLLs', async () => {
  const {runtime,calls} = runtimeFixture({wow64:false}); await runtime.boot();
  await assert.rejects(runtime.launch(collectFiles([exe('game.exe',332)]),'game.exe'),/WoW64/);
  assert.equal(calls.filter(c=>c[0]==='spawn').length,0);
});
