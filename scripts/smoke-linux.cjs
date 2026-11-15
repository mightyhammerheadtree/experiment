// Opt-in integration test against operator-staged linuxontab linux4.iso assets.
// Runs actual v86 Wasm and Linux in Node; does NOT test browser rendering or Wine.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(process.argv[2] || 'work/windex-linux/assets/linux');
const {V86} = require(path.join(root, 'libv86.js'));
let output = '', sentUname = false, sentFile = false, finished = false;
const asset = name => ({url: path.join(root, name)});
const vm = new V86({wasm_path: path.join(root, 'v86.wasm'), bios: asset('seabios.bin'), vga_bios: asset('vgabios.bin'), cdrom: asset('linux4.iso'), memory_size: 128*1024*1024, vga_memory_size: 4*1024*1024, filesystem: {}, disable_speaker: true, autostart: true});
const timer = setTimeout(() => finish(1, 'Timed out waiting for Linux uname and 9P transfer'), 60000);
function finish(code, message) {
  if (finished) return;
  finished = true; clearTimeout(timer);
  console.log(output.slice(-4000)); console.log(message);
  vm.stop(); setTimeout(() => process.exit(code), 100);
}
vm.add_listener('serial0-output-byte', byte => {
  output += String.fromCharCode(byte);
  if (!sentUname && output.includes('~%')) { sentUname = true; vm.serial0_send('uname -a\n'); }
  if (!sentFile && /Linux .* 4\.16\.13 .* i686/.test(output)) {
    sentFile = true;
    vm.create_file('/windex-smoke.txt', new TextEncoder().encode('WINDEX_BRIDGE_OK\n'))
      .then(() => vm.serial0_send('cat /mnt/windex-smoke.txt\n'))
      .catch(error => finish(1, error.message));
  }
  if (sentFile && output.includes('WINDEX_BRIDGE_OK')) finish(0, 'PASS: real Linux kernel uname and explicit host→9P file transfer (Node/v86, not browser/Wine)');
});
