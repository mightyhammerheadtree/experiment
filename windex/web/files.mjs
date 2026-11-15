// Browser-only file handling: game bytes are never posted to the hosting server.
export function relativePath(value) {
  if (typeof value !== 'string' || !value || value.startsWith('/') || value.includes('\\') || /[\x00-\x1f:]/.test(value)) throw Error('Unsafe relative filename');
  if (value.split('/').some(p => !p || p === '.' || p === '..')) throw Error('Unsafe path segment');
  return value;
}
export function collectFiles(files, {folder = false, limit = 1024 ** 3} = {}) {
  const entries = Array.from(files, file => ({ file, path: relativePath(file.webkitRelativePath || file.name) }));
  if (!entries.length || entries.length > 10000) throw Error('Select between 1 and 10,000 files');
  if (entries.reduce((n, e) => n + e.file.size, 0) > limit) throw Error('Selected files exceed the 1 GiB import limit');
  if (folder) {
    const root = entries[0].path.split('/')[0];
    if (!entries.every(e => e.path.startsWith(root + '/'))) throw Error('Select one game folder');
    for (const entry of entries) entry.path = relativePath(entry.path.slice(root.length + 1));
  }
  const seen = new Set();
  for (const {path} of entries) {
    if (seen.has(path.toLowerCase())) throw Error('Case-insensitive duplicate file: ' + path);
    seen.add(path.toLowerCase());
  }
  return entries;
}
export async function peArchitecture(file) {
  const head = new DataView(await file.slice(0, 64).arrayBuffer());
  if (head.byteLength < 64 || head.getUint16(0, true) !== 0x5a4d) throw Error('Not a Windows PE executable');
  const offset = head.getUint32(0x3c, true);
  if (offset > file.size - 6) throw Error('Truncated PE header');
  const pe = new DataView(await file.slice(offset, offset + 6).arrayBuffer());
  if (pe.getUint32(0, true) !== 0x4550) throw Error('Invalid PE signature');
  const arch = {332: 'x86', 34404: 'x64'}[pe.getUint16(4, true)];
  if (!arch) throw Error('This runtime targets x64 and x86 Windows programs only');
  return arch;
}
export function localURL(path, base = globalThis.location?.href || 'http://localhost/') {
  const url = new URL(path, base);
  if (url.origin !== new URL(base).origin || !['http:', 'https:'].includes(url.protocol)) throw Error('Runtime assets must be same-origin HTTP(S)');
  return url.href;
}
