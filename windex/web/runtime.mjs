import {localURL, relativePath, peArchitecture} from './files.mjs';
import {inspectWine, memory64Supported} from './wine.mjs';

// Adapter for GEX's real public System API. This is runtime translation, not eject.
export class WindowsRuntime extends EventTarget {
  constructor(config, {load = url => import(url), platform, onWindow = () => {}} = {}) {
    super(); this.config = config; this.load = load; this.onWindow = onWindow;
    this.platform = platform || {isolated: globalThis.crossOriginIsolated, gpu: !!globalThis.navigator?.gpu, opfs: !!globalThis.navigator?.storage?.getDirectory};
    this.state = 'idle'; this.process = null; this.audio = null; this.used = false; this.wine = null; this.diagnostics = []; this.wineTest = null;
  }
  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, {detail})); }
  setState(state) { this.state = state; this.emit('state', state); }
  async boot({persistent = false} = {}) {
    if (this.used) throw Error('One GEX System per page; reload to start a new session');
    if (!this.config.enabled) throw Error('GEX + Wine runtime assets have not been staged. This deployment needs its compiled browser runtime assets.');
    if (!this.platform.isolated) throw Error('Cross-origin isolation is required. Use the Windex server or send COOP/COEP headers.');
    if (this.config.d3d && !this.platform.gpu) throw Error('This graphics profile requires WebGPU. Use a supported browser/device.');
    if (persistent && !this.platform.opfs) throw Error('Persistent storage is unavailable; choose an in-memory session');
    if (!Array.isArray(this.config.trees) || !this.config.trees.length) throw Error('A GEX-compatible filesystem with Wasm Wine and a prefix is required');
    const base = localURL(this.config.package);
    this.used = true; this.setState('booting');
    this.report('runtime-modules', 'checking', 'Loading GEX browser modules');
    try {
      const [runtime, fs, windows, gl, audio, input] = await Promise.all(['index','fs','windows-host','gl','audio','input'].map(n => this.load(new URL(n+'.mjs', base).href)));
      this.report('runtime-modules', 'pass', 'GEX modules loaded');
      this.system = new runtime.System({arch: 'x86', xcache: true});
      this.system.addEventListener('console', e => this.emit('log', e.text || ''));
      this.system.addEventListener('crash', e => this.emit('log', `Crash: ${e.name || ''} ${e.reason || ''}`));
      this.filesystem = persistent ? new fs.OPFSFilesystem(this.system, {name: this.config.store}) : new fs.MemoryFilesystem(this.system);
      for (const tree of this.config.trees) this.filesystem.addTar(localURL(tree));
      this.windows = new windows.HostWindows(this.system, {width: 1280, height: 720});
      this.windows.addEventListener('window', e => this.onWindow(e.window));
      this.gl = new gl.MesaGl(this.system, {d3d: !!this.config.d3d});
      this.gl.addEventListener?.('failed', e => this.emit('log', 'Graphics: ' + e.error?.message));
      this.Audio = audio.WebAudio;
      this.gamepads = new input.Gamepads(this.system);
      this.pointer = new input.PointerLock(this.system);
      // Intentionally no network/Wisp or clipboard adapter: no hidden relay.
      this.report('kernel', 'checking', 'Starting GEX kernel and mounting filesystem layers');
      await this.system.boot();
      this.report('kernel', 'pass', 'GEX kernel booted');
      this.setState('checking-wine');
      try { await this.checkWine(); } catch (e) {
        if (e.code !== 'WINE_NOT_READY') throw e;
        this.emit('log', e.message + '\nInstall a compatible Wasm Wine runtime bundle in this browser session.\n');
        this.setState('needs-wine'); return;
      }
      this.emit('log', 'Wine files ready; use Test Wine to verify actual execution before trying a game.\n');
      this.setState('ready');
    } catch (e) { this.setState('failed'); throw e; }
  }
  async checkWine() {
    this.wine = await inspectWine(this.filesystem, this.config, check => this.report(check.id, check.status, check.detail));
    return this.wine;
  }
  async installWine(layers) {
    if (!['needs-wine', 'ready'].includes(this.state)) throw Error('Boot the GEX environment and stop running programs before installing Wine');
    const files = Array.from(layers);
    if (!files.length || files.some(f => !/\.tar(?:\.zst)?$/i.test(f.name))) throw Error('Choose compatible Wine .tar or .tar.zst runtime layers');
    if (files.reduce((n,f) => n+f.size,0) > 1024**3) throw Error('Runtime layers exceed the 1 GiB selection limit');
    this.setState('installing-wine'); this.wineTest = null;
    try {
      for (let i=0; i<files.length; i++) {
        this.report('wine-install', 'checking', 'Applying runtime layer '+files[i].name);
        await this.filesystem.addTar(files[i]);
        this.emit('progress', {stage:'installing-wine', file:files[i].name, imported:i+1, total:files.length});
      }
      await this.checkWine();
      await this.system.sync();
      this.report('wine-install', 'pass', 'Wine runtime layers installed; execution test still required');
      this.setState('ready');
    } catch (e) { this.wine = null; this.report('wine-install', 'fail', e.message); this.setState('needs-wine'); throw e; }
  }
  report(id, status, detail) {
    const row = {id, status, detail};
    this.diagnostics = this.diagnostics.filter(c => c.id !== id).concat(row);
    this.emit('diagnostic', row);
  }
  environment(arch = 'x64') {
    return {...this.config.env, ...this.windows.env, WINEPREFIX:this.config.prefix, WINEGEX_WOW64:this.wine?.wow64 ? '1' : '0', ...(arch === 'x64' ? {GEX_MEM64:'1'} : {GEX_MEM64:'0'})};
  }
  async testWine({timeoutMs = 15000} = {}) {
    if (this.state !== 'ready') throw Error('Start the runtime and wait for it to be ready');
    this.setState('testing-wine'); this.wineTest = null;
    this.report('wine-execution', 'checking', 'Running Wine cmd.exe /c ver in the browser');
    let timer, timedOut = false; const output = [];
    try {
      const process = this.system.spawn([this.config.loader, 'cmd.exe', '/c', 'ver'], {env:this.environment(), cwd:this.config.prefix});
      this.process = process;
      const completion = process.exited; completion.catch(() => {});
      const capture = text => { if (output.join('').length < 64000) output.push(text.slice(0, 64000)); };
      this.drain(process.stdout, capture); this.drain(process.stderr, capture);
      const result = await Promise.race([
        (async () => { await process.started; return completion; })(),
        new Promise((_, reject) => { timer = setTimeout(() => { timedOut = true; try { process.kill('SIGTERM'); } catch {} reject(Error('Wine execution test timed out; reload the session before retrying')); }, timeoutMs); })
      ]);
      if (result.code !== 0) throw Error('Wine cmd.exe failed with exit code ' + result.code);
      this.wineTest = {status:'passed', code:result.code, output:output.join('').slice(0, 64000)};
      this.report('wine-execution', 'pass', 'Wine cmd.exe /c ver exited successfully; game compatibility is not implied');
      this.emit('log', this.wineTest.output + '\n'); return this.wineTest;
    } catch (e) {
      this.wineTest = {status:'failed', error:e.message}; this.report('wine-execution', 'fail', e.message); throw e;
    } finally { clearTimeout(timer); this.process = null; this.setState(timedOut ? 'failed' : 'ready'); }
  }
  async launch(entries, executable) {
    if (this.state !== 'ready') throw Error('Boot Windows runtime first; only one foreground program at a time');
    const chosen = entries.find(e => e.path === executable);
    if (!chosen) throw Error('Choose an EXE from the imported files');
    relativePath(executable);
    // Construct audio synchronously in the Run button's user gesture.
    this.audio ||= new this.Audio(this.system);
    this.audio.ready.catch(e => this.emit('log', 'Audio: '+e.message));
    this.setState('importing');
    try {
      const arch = await peArchitecture(chosen.file);
      if (arch === 'x86' && !this.wine.wow64) throw Error('This Wine installation has no WoW64 support for x86 games');
      if (arch === 'x64' && !memory64Supported()) throw Error('This x64 runtime profile requires browser WebAssembly memory64 support');
      const exeBytes = new Uint8Array(await chosen.file.arrayBuffer());
      const hash = new Uint8Array(await crypto.subtle.digest('SHA-256', exeBytes));
      const root = '/games/' + [...hash].map(byte => byte.toString(16).padStart(2, '0')).join('');
      await this.filesystem.mkdir(root, {recursive: true});
      let imported = 0, loadedBytes = 0;
      const totalBytes = entries.reduce((n, e) => n + e.file.size, 0);
      for (const entry of entries) {
        const path = root + '/' + relativePath(entry.path);
        await this.filesystem.mkdir(path.slice(0, path.lastIndexOf('/')), {recursive: true});
        await this.filesystem.writeFile(path, entry === chosen ? exeBytes : new Uint8Array(await entry.file.arrayBuffer()));
        loadedBytes += entry.file.size; imported++;
        this.emit('progress', {stage:'importing', file:entry.path, imported, total:entries.length, loadedBytes, totalBytes});
      }
      const file = root + '/' + executable;
      const cwd = file.slice(0, file.lastIndexOf('/'));
      const env = this.environment(arch);
      const argv = [this.config.loader, 'Z:' + file.replaceAll('/', '\\')];
      this.emit('log', `Launching ${arch}: ${executable} (runtime translation, not static recompilation)`);
      this.setState('starting');
      const process = this.system.spawn(argv, {cwd, env});
      this.process = process;
      const completion = process.exited;
      completion.catch(() => {});
      this.drain(process.stdout); this.drain(process.stderr);
      await process.started;
      this.setState('running');
      completion.then(status => {
        if (this.process === process) { this.process = null; this.setState('ready'); }
        this.emit('exit', status);
      }, error => {
        if (this.process === process) { this.process = null; this.setState('ready'); }
        this.emit('log', 'Program failed: ' + error.message);
      });
    } catch (e) { this.process = null; this.setState('ready'); throw e; }
  }
  async drain(stream, capture = null) {
    if (!stream) return;
    const reader = stream.getReader(), decoder = new TextDecoder();
    try {
      while (true) { const {done, value} = await reader.read(); if (done) break; const text = decoder.decode(value, {stream: true}); capture?.(text); this.emit('log', text); }
      const tail = decoder.decode(); if (tail) { capture?.(tail); this.emit('log', tail); }
    } catch (e) { this.emit('log', 'Pipe: ' + e.message); }
    finally { reader.releaseLock(); }
  }
  stop() { if (this.process) this.process.kill('SIGTERM'); }
  async shutdown() {
    if (!this.system) return;
    await this.system.shutdown(); this.process = null; this.setState('stopped');
  }
}
