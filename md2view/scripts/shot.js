#!/usr/bin/env node
// 视觉校验环截图工具。用法: node shot.js <html> <out-dir> [selector ...]
// 截整页 fullPage + 可选逐 selector 截图。需 playwright。
const path = require('path');
const fs = require('fs');
let chromium;
try { ({ chromium } = require('@playwright/test')); }
catch (e) {
  try { ({ chromium } = require('playwright')); }
  catch (e2) {
    console.error('[shot] 需要 playwright：npm i -g playwright && npx playwright install chromium');
    console.error('       或 cd 到任意已装 @playwright/test 的项目再跑本脚本。');
    process.exit(1);
  }
}
(async () => {
  const [html, outDir, ...sels] = process.argv.slice(2);
  if (!html || !outDir) { console.error('用法: node shot.js <html> <out-dir> [#v1 #v2 ...]'); process.exit(1); }
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1.5 });
  await page.goto('file://' + path.resolve(html));
  await page.waitForTimeout(500);
  await page.evaluate(() => document.querySelectorAll('section.view').forEach(s => s.classList.add('in')));
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(outDir, 'full.png'), fullPage: true });
  for (const sel of sels) {
    const el = await page.$(sel);
    if (el) await el.screenshot({ path: path.join(outDir, sel.replace(/[^\w]/g, '') + '.png') });
    else console.warn('[shot] 未找到', sel);
  }
  await browser.close();
  console.log('[shot] 截图完成 ->', outDir);
})();
