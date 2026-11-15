import {collectFiles} from './files.mjs';
import {WindowsRuntime} from './runtime.mjs';
import {LinuxConsole} from './linux.mjs';
const $ = id => document.getElementById(id);
let entries = [], runtime, linux, noticeTimer, z = 1;
function notify(message) { $('message').textContent = message; $('message').style.display = 'block'; clearTimeout(noticeTimer); noticeTimer = setTimeout(() => $('message').style.display = 'none', 10000); }
function append(id, text, max = 64000) { const node = $(id); node.textContent = (node.textContent + text).slice(-max); node.scrollTop = node.scrollHeight; }
function busyFiles() { return runtime && !['idle','ready'].includes(runtime.state); }
function refresh() { const ready = runtime?.state === 'ready'; $('run').disabled = !ready || !$('exe').value; $('stop').disabled = runtime?.state !== 'running'; $('boot').disabled = !runtime?.config.enabled || runtime.state !== 'idle'; $('persist').disabled = runtime?.state !== 'idle'; $('installWine').disabled = !['needs-wine','ready'].includes(runtime?.state); $('testWine').disabled = !ready; $('filesButton').disabled = busyFiles(); $('folderButton').disabled = busyFiles(); }
function choose(files, folder = false) {
  if (busyFiles()) return notify('Wait for the running program to end before changing game files');
  try { entries = collectFiles(files, {folder}); $('exe').replaceChildren(); const exes = entries.filter(e => /\.exe$/i.test(e.path)); for (const entry of exes) { const option = document.createElement('option'); option.value = entry.path; option.textContent = entry.path; $('exe').append(option); } $('exe').disabled = !exes.length; $('fileStatus').textContent = `${entries.length} files · ${(entries.reduce((n,e)=>n+e.file.size,0)/1048576).toFixed(1)} MiB · ${exes.length} executables. Local browser selection only.`; refresh(); }
  catch (e) { notify(e.message); }
}
$('folderButton').onclick = () => $('folderInput').click(); $('filesButton').onclick = () => $('filesInput').click();
$('folderInput').onchange = e => choose(e.target.files, true); $('filesInput').onchange = e => choose(e.target.files);
$('exe').onchange = refresh;
$('drop').ondragover = e => { e.preventDefault(); $('drop').classList.add('over'); }; $('drop').ondragleave = () => $('drop').classList.remove('over');
$('drop').ondrop = e => { e.preventDefault(); $('drop').classList.remove('over'); if ([...e.dataTransfer.items].some(i => i.webkitGetAsEntry?.()?.isDirectory)) return notify('Use Choose game folder to preserve directories'); choose(e.dataTransfer.files); };
for (const button of document.querySelectorAll('[data-view]')) button.onclick = () => { for (const view of document.querySelectorAll('.view')) view.hidden = view.id !== button.dataset.view; for (const nav of document.querySelectorAll('.nav')) nav.classList.toggle('active', nav === button); $('breadcrumb').textContent = 'Workspace / ' + button.textContent.trim().slice(1).trim(); };
function showWindow(w) {
  $('emptyDisplay').hidden = true;
  const element = document.createElement('div'); element.className = 'guest-window'; element.style.zIndex = ++z;
  const title = document.createElement('header'), label = document.createElement('span'), close = document.createElement('button');
  label.textContent = w.title || 'Wine program'; close.textContent = '×'; close.setAttribute('aria-label','Close guest window'); close.onclick = () => w.close(); title.append(label,close);
  if (w.decorations === 'host') element.append(title);
  element.append(w.canvas); $('desktop').append(element);
  let x = w.x || 0, y = w.y || 0;
  const position = () => { element.style.left = x + 'px'; element.style.top = y + 'px'; };
  const nativePosition = () => { x = w.x || 0; y = w.y || 0; position(); };
  position(); w.addEventListener('position', nativePosition);
  w.addEventListener('title', () => label.textContent = w.title || 'Wine program');
  w.addEventListener('closed', () => { element.remove(); if (!$('desktop').querySelector('.guest-window')) $('emptyDisplay').hidden = false; });
  element.onpointerdown = () => element.style.zIndex = ++z;
  title.onpointerdown = e => { if (e.target === close) return; const startX = e.clientX - x, startY = e.clientY - y; title.setPointerCapture(e.pointerId); title.onpointermove = move => { x = Math.max(0, move.clientX-startX); y = Math.max(0, move.clientY-startY); position(); w.place(x, y); }; title.onpointerup = () => title.onpointermove = null; };
  const resize = () => { $('desktop').style.minHeight = Math.max(270, ...[...$('desktop').querySelectorAll('canvas')].map(c => c.height / (devicePixelRatio || 1) + 40)) + 'px'; };
  w.addEventListener('resized', resize); resize();
  w.addEventListener('request', e => { if (['maximize','fullscreen'].includes(e.kind)) w.setStates({maximized: true}, $('desktop').clientWidth, 720); if (['unmaximize','unfullscreen'].includes(e.kind)) w.setStates({maximized: false, fullscreen: false}); });
}
$('boot').onclick = async () => { try { await runtime.boot({persistent: $('persist').checked}); append('runtimeLog', runtime.state === 'ready' ? 'Wine files ready. Test Wine, then select a game.\n' : 'GEX environment started. Install a compatible Wine runtime bundle to enable Windows games.\n'); } catch (e) { notify(e.message); append('runtimeLog', e.message+'\n'); } refresh(); };
$('run').onclick = async () => { try { await runtime.launch(entries, $('exe').value); } catch (e) { notify(e.message); append('runtimeLog', e.message+'\n'); } refresh(); };
$('stop').onclick = () => runtime.stop();
$('installWine').onclick = () => $('wineLayers').click();
$('wineLayers').onchange = async e => { try { await runtime.installWine(e.target.files); notify('Wine files installed. Use Test Wine to verify execution.'); } catch (error) { notify(error.message); } finally { e.target.value = ''; refresh(); } };
$('testWine').onclick = async () => { try { await runtime.testWine(); notify('Wine execution test passed. Game compatibility still varies.'); } catch (e) { notify(e.message); } refresh(); };
$('linuxBoot').onclick = async () => { try { await linux.boot($('vga')); } catch (e) { notify(e.message); } };
$('linuxStop').onclick = () => linux.stop().catch(e => notify(e.message));
$('terminalForm').onsubmit = e => { e.preventDefault(); try { linux.send($('terminalInput').value + '\n'); $('terminalInput').value = ''; } catch (e) { notify(e.message); } };
$('interrupt').onclick = () => { try { linux.send('\x03'); } catch (e) { notify(e.message); } };
$('transfer').onclick = async () => { try { const file = $('linuxFile').files[0]; if (!file) throw Error('Choose a file first'); await linux.transfer(file); } catch (e) { notify(e.message); } };
try {
  const response = await fetch('./windex.json'); if (!response.ok) throw Error('Missing Windex configuration. Stage a site first.'); const config = await response.json();
  runtime = new WindowsRuntime(config.gex, {onWindow: showWindow}); linux = new LinuxConsole(config.linux);
  runtime.addEventListener('state', e => { $('runtimeState').textContent = e.detail.toUpperCase(); refresh(); });
  runtime.addEventListener('diagnostic', () => { $('diagnostics').replaceChildren(); for (const row of runtime.diagnostics) { const item = document.createElement('li'); item.className = row.status; item.textContent = `${row.status.toUpperCase()} · ${row.detail}`; $('diagnostics').append(item); } });
  runtime.addEventListener('progress', e => { const p = e.detail; $('importProgress').textContent = `${p.stage}: ${p.imported}/${p.total} · ${p.file}`; });
  runtime.addEventListener('log', e => append('runtimeLog', e.detail)); runtime.addEventListener('exit', e => append('runtimeLog', '\nProgram exited: '+JSON.stringify(e.detail)+'\n'));
  linux.addEventListener('output', e => append('serial', e.detail, 200000)); linux.addEventListener('state', e => { $('linuxState').textContent = e.detail.toUpperCase(); $('linuxBoot').disabled = e.detail !== 'idle'; $('linuxStop').disabled = e.detail !== 'running'; });
  $('gexAvailability').textContent = config.gex.enabled ? 'GEX environment configured. Boot it to check Wine availability.' : 'This deployment has not supplied its GEX runtime. No game is simulated.';
  $('linuxAvailability').textContent = config.linux.enabled ? 'Local v86/BIOS/ISO assets staged. Network relay is disabled.' : 'Not staged: use --linuxontab with the Windex stage command.';
  $('linuxBoot').disabled = !config.linux.enabled;
  $('capabilities').textContent = JSON.stringify({secureContext: isSecureContext, crossOriginIsolated, WebGPU: !!navigator.gpu, OPFS: !!navigator.storage?.getDirectory, gexAssetsConfigured: config.gex.enabled, linuxAssetsConfigured: config.linux.enabled}, null, 2);
  refresh();
} catch (e) { notify(e.message); append('runtimeLog', e.message+'\n'); $('boot').disabled = true; $('linuxBoot').disabled = true; }
