// Integration check against a running Windex deployment, using real npm GEX assets.
import chromium from '@sparticuz/chromium';
import {chromium as playwright} from 'playwright-core';
import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {brotliDecompressSync} from 'node:zlib';
import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';

// Minimal Linux CI images may lack NSS. The browser package bundles these libraries.
const libs = resolve('.cache/browser-libs');
if (process.platform === 'linux') {
  await mkdir(libs, {recursive:true});
  await writeFile(resolve('.cache/browser-libs.tar'), brotliDecompressSync(await readFile(new URL('../node_modules/@sparticuz/chromium/bin/al2023.tar.br', import.meta.url))));
  execFileSync('tar', ['-xf', resolve('.cache/browser-libs.tar'), '-C', libs]);
}
// Do not use the package's disable-web-security defaults: they invalidate COOP/COEP testing.
const args = chromium.args.filter(a => !a.includes('disable-web-security') && !a.includes('disable-site-isolation') && !a.includes('disable-features=') && a !== '--single-process');
const browser = await playwright.launch({args:[...args,'--enable-unsafe-webgpu'], executablePath:await chromium.executablePath(), headless:true, env:{...process.env, LD_LIBRARY_PATH:[resolve(libs,'lib'),process.env.LD_LIBRARY_PATH].filter(Boolean).join(':')}});
try {
  const page = await browser.newPage();
  page.on('pageerror', e => console.error(e));
  await page.goto(process.env.WINDEX_URL || 'http://127.0.0.1:8080/');
  assert.equal(await page.evaluate(() => crossOriginIsolated), true, 'Deployment must be cross-origin isolated');
  await page.locator('#boot').click();
  await page.waitForFunction(() => ['NEEDS-WINE','READY','FAILED'].includes(document.querySelector('#runtimeState').textContent), {}, {timeout:60000});
  const state = await page.locator('#runtimeState').textContent();
  const diagnostics = await page.locator('#diagnostics').textContent();
  console.log(state, diagnostics);
  assert.notEqual(state, 'FAILED');
  assert.match(diagnostics, /GEX kernel booted/);
  if (state === 'NEEDS-WINE') assert.match(diagnostics, /Missing guest file/);
  console.log('Real browser GEX boot passed. Wine/game execution is NOT verified by this test.');
} finally { await browser.close(); }
