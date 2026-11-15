import {localURL} from './files.mjs';

// v86/Linux is a separate VM, not GEX's syscall kernel or an x64 backend.
export class LinuxConsole extends EventTarget {
  constructor(config) { super(); this.config = config; this.emulator = null; this.state = 'idle'; }
  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, {detail})); }
  async boot(screen) {
    if (this.state !== 'idle') throw Error('Linux VM already started; reload to create a fresh VM');
    if (!this.config.enabled) throw Error('Stage linuxontab/v86 assets first');
    this.state = 'booting'; this.emit('state', this.state);
    try {
      const base = localURL(this.config.assets);
      if (!globalThis.V86) await new Promise((resolve, reject) => {
        const script = document.createElement('script'); script.src = new URL('libv86.js', base).href;
        script.onload = resolve; script.onerror = () => reject(Error('Could not load v86')); document.head.append(script);
      });
      const emulator = new globalThis.V86({wasm_path: new URL('v86.wasm', base).href, bios: {url: new URL('seabios.bin', base).href}, vga_bios: {url: new URL('vgabios.bin', base).href}, cdrom: {url: new URL(this.config.iso, base).href}, memory_size: this.config.memoryMiB * 1024 * 1024, vga_memory_size: 4 * 1024 * 1024, screen_container: screen, filesystem: {}, autostart: true, disable_mouse: true, disable_keyboard: true, disable_speaker: true});
      this.emulator = emulator;
      emulator.add_listener('serial0-output-byte', byte => this.emit('output', String.fromCharCode(byte)));
      emulator.add_listener('emulator-ready', () => { this.state = 'running'; this.emit('state', this.state); });
    } catch (e) { this.state = 'failed'; this.emit('state', this.state); throw e; }
  }
  send(text) { if (this.state !== 'running') throw Error('Linux VM is not running'); this.emulator.serial0_send(text); }
  async transfer(file) {
    if (this.state !== 'running') throw Error('Linux VM is not running');
    if (!file || file.size > 256*1024*1024) throw Error('Choose a file up to 256 MiB');
    const name = 'windex-' + file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
    await this.emulator.create_file('/' + name, new Uint8Array(await file.arrayBuffer()));
    this.emit('output', `\n[Windex] ${name} copied to the separate 9P filesystem.\nlinux4.iso normally exposes this at /mnt. If not mounted, use: mkdir -p /mnt/windex; mount -t 9p -o trans=virtio host9p /mnt/windex\n`);
    return name;
  }
  async stop() { if (this.emulator) await this.emulator.stop(); this.state = 'stopped'; this.emit('state', this.state); }
}
