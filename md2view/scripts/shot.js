#!/usr/bin/env node
// 视觉校验环截图 + smoke 回归工具。
// 用法:
//   node shot.js <html> <out-dir> [selector ...]
//   node shot.js <html> <out-dir> --viewports=1440,1280,1024,768 "#v1" "#v2"
// 环境变量:
//   MD2VIEW_VIEWPORTS=1440,1280,1024,768
//   MD2VIEW_HEIGHT=900
//   MD2VIEW_ASSERT=0      仅截图，不跑 smoke assertions
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

function usage() {
  console.error('用法: node shot.js <html> <out-dir> [--viewports=1440,1280,1024,768] [--height=900] [--no-assert] [#v1 #v2 ...]');
}

function parseArgs(argv) {
  const [html, outDir, ...rest] = argv;
  if (!html || !outDir) {
    usage();
    process.exit(1);
  }

  const selectors = [];
  const viewportsFromEnv = process.env.MD2VIEW_VIEWPORTS || '1440,1280,1024,768';
  let viewports = viewportsFromEnv.split(',').map(v => Number(v.trim())).filter(Boolean);
  let height = Number(process.env.MD2VIEW_HEIGHT || 900);
  let assertions = process.env.MD2VIEW_ASSERT !== '0';

  for (const arg of rest) {
    if (arg.startsWith('--viewports=')) {
      viewports = arg.slice('--viewports='.length).split(',').map(v => Number(v.trim())).filter(Boolean);
    } else if (arg.startsWith('--height=')) {
      height = Number(arg.slice('--height='.length));
    } else if (arg === '--no-assert') {
      assertions = false;
    } else if (arg === '--assert') {
      assertions = true;
    } else {
      selectors.push(arg);
    }
  }

  if (!viewports.length || viewports.some(v => !Number.isFinite(v) || v < 320)) {
    throw new Error('[shot] viewports 必须是 >=320 的数字列表');
  }
  if (!Number.isFinite(height) || height < 480) {
    throw new Error('[shot] height 必须是 >=480 的数字');
  }

  return { html, outDir, selectors, viewports, height, assertions };
}

function safeName(input) {
  return input.replace(/[^\w-]+/g, '_').replace(/^_+|_+$/g, '') || 'selector';
}

async function assertLocator(page, selector, label) {
  const count = await page.locator(selector).count();
  if (!count) throw new Error(`[shot] 缺少 ${label}: ${selector}`);
  return count;
}

async function collectEdgeHealth(page) {
  return page.$$eval('.mv-edge-path', paths => paths.map((pathEl, index) => {
    const d = pathEl.getAttribute('d') || '';
    const numbers = d.match(/-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?/gi) || [];
    let totalLength = null;
    let lengthError = null;
    try {
      totalLength = typeof pathEl.getTotalLength === 'function' ? pathEl.getTotalLength() : null;
    } catch (err) {
      lengthError = String(err && err.message || err);
    }
    const flow = pathEl.closest('[data-flow]');
    const from = flow && flow.querySelector(`.mv-node[data-node-id="${CSS.escape(pathEl.dataset.from || '')}"]`);
    const to = flow && flow.querySelector(`.mv-node[data-node-id="${CSS.escape(pathEl.dataset.to || '')}"]`);
    let startGap = null;
    let endGap = null;
    let withinLayer = false;
    let crossesNode = false;
    const borderDistance = (point, rect) => {
      const x = point.x;
      const y = point.y;
      const horizontal = Math.min(
        Math.hypot(x - rect.left, y < rect.top ? rect.top - y : y > rect.bottom ? y - rect.bottom : 0),
        Math.hypot(x - rect.right, y < rect.top ? rect.top - y : y > rect.bottom ? y - rect.bottom : 0),
      );
      const vertical = Math.min(
        Math.hypot(y - rect.top, x < rect.left ? rect.left - x : x > rect.right ? x - rect.right : 0),
        Math.hypot(y - rect.bottom, x < rect.left ? rect.left - x : x > rect.right ? x - rect.right : 0),
      );
      return Math.min(horizontal, vertical);
    };
    if (flow && from && to && Number.isFinite(totalLength) && totalLength > 0) {
      const start = pathEl.getPointAtLength(0);
      const end = pathEl.getPointAtLength(totalLength);
      const matrix = pathEl.getScreenCTM();
      const startViewport = new DOMPoint(start.x, start.y).matrixTransform(matrix);
      const endViewport = new DOMPoint(end.x, end.y).matrixTransform(matrix);
      startGap = borderDistance(startViewport, from.getBoundingClientRect());
      endGap = borderDistance(endViewport, to.getBoundingClientRect());
      const box = pathEl.getBBox();
      withinLayer = box.x >= -1 && box.y >= -1 && box.x + box.width <= flow.clientWidth + 1 && box.y + box.height <= flow.clientHeight + 1;
      const otherNodes = [...flow.querySelectorAll('.mv-node')].filter(node => node !== from && node !== to);
      for (let step = 1; step < 32 && !crossesNode; step += 1) {
        const sample = pathEl.getPointAtLength(totalLength * step / 32);
        const viewportPoint = new DOMPoint(sample.x, sample.y).matrixTransform(matrix);
        crossesNode = otherNodes.some(node => {
          const rect = node.getBoundingClientRect();
          return viewportPoint.x > rect.left + 2 && viewportPoint.x < rect.right - 2 &&
            viewportPoint.y > rect.top + 2 && viewportPoint.y < rect.bottom - 2;
        });
      }
    }
    return {
      index,
      d,
      numberCount: numbers.length,
      finiteNumbers: numbers.every(n => Number.isFinite(Number(n))),
      totalLength,
      lengthError,
      startGap,
      endGap,
      withinLayer,
      crossesNode,
    };
  }));
}

async function runAssertions(page, width) {
  await assertLocator(page, '[data-md2view-split]', '双栏容器');
  await assertLocator(page, '[data-md2view-status]', '状态反馈节点');

  const separator = page.locator('[data-md2view-separator]').first();
  if (!await separator.count()) throw new Error('[shot] 缺少可调宽分隔条: [data-md2view-separator]');
  const sepAttrs = await separator.evaluate(el => ({
    role: el.getAttribute('role'),
    tabindex: el.getAttribute('tabindex'),
    orientation: el.getAttribute('aria-orientation'),
    min: el.getAttribute('aria-valuemin'),
    max: el.getAttribute('aria-valuemax'),
    now: el.getAttribute('aria-valuenow'),
  }));
  if (sepAttrs.role !== 'separator') throw new Error('[shot] 分隔条 role 必须是 separator');
  if (sepAttrs.orientation !== 'vertical') throw new Error('[shot] 分隔条 aria-orientation 必须是 vertical');
  if (sepAttrs.tabindex === null) throw new Error('[shot] 分隔条需要 tabindex 支持键盘聚焦');
  for (const [name, value] of Object.entries({ min: sepAttrs.min, max: sepAttrs.max, now: sepAttrs.now })) {
    if (!Number.isFinite(Number(value))) throw new Error(`[shot] 分隔条 aria-value${name} 必须是有限数值`);
  }

  if (await separator.isVisible()) {
    const before = Number(await separator.getAttribute('aria-valuenow'));
    await separator.focus();
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(100);
    const afterKey = Number(await separator.getAttribute('aria-valuenow'));
    if (!(afterKey > before)) throw new Error(`[shot] 分隔条 ArrowRight 未增加栏宽: ${before} -> ${afterKey}`);

    const splitBox = await page.locator('[data-md2view-split]').boundingBox();
    const sepBox = await separator.boundingBox();
    if (!splitBox || !sepBox) throw new Error('[shot] 无法读取分隔条几何');
    await page.mouse.move(sepBox.x + sepBox.width / 2, sepBox.y + sepBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(splitBox.x + splitBox.width * 0.48, sepBox.y + sepBox.height / 2, { steps: 5 });
    await page.mouse.up();
    await page.waitForTimeout(140);
    const afterDrag = Number(await separator.getAttribute('aria-valuenow'));
    if (Math.abs(afterDrag - 48) > 2) throw new Error(`[shot] 分隔条拖拽未到目标比例: ${afterDrag}%`);

    await page.reload();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(420);
    const restored = Number(await separator.getAttribute('aria-valuenow'));
    if (Math.abs(restored - afterDrag) > 1) throw new Error(`[shot] 分隔比例未跨刷新恢复: ${afterDrag}% -> ${restored}%`);
    await separator.dblclick();
    await page.waitForTimeout(100);
    const reset = Number(await separator.getAttribute('aria-valuenow'));
    if (Math.abs(reset - 42) > 1) throw new Error(`[shot] 双击未恢复默认栏宽: ${reset}%`);
  }

  const modes = page.locator('[data-md2view-mode]');
  const modeCount = await modes.count();
  if (modeCount < 3) throw new Error(`[shot] 模式按钮不足，期望至少 3 个，实际 ${modeCount}`);
  let visibleModeCount = 0;
  for (let i = 0; i < modeCount; i += 1) {
    const mode = modes.nth(i);
    if (!await mode.isVisible()) continue;
    visibleModeCount += 1;
    await mode.click();
    await page.waitForTimeout(80);
    const active = await mode.evaluate(el => {
      const aria = el.getAttribute('aria-pressed');
      return aria === 'true' || el.classList.contains('on') || el.classList.contains('is-active');
    });
    if (!active) throw new Error(`[shot] 第 ${i + 1} 个模式按钮点击后没有激活状态`);
    const modeName = await mode.getAttribute('data-md2view-mode');
    if (modeName === 'l' || modeName === 'r') {
      const paneBox = await page.locator(modeName === 'l' ? '#paneL' : '#paneR').boundingBox();
      const viewportWidth = page.viewportSize().width;
      if (!paneBox || Math.abs(paneBox.x) > 1 || Math.abs(paneBox.width - viewportWidth) > 2) {
        throw new Error(`[shot] ${modeName} 单栏未铺满视口: ${JSON.stringify(paneBox)} / ${viewportWidth}px`);
      }
    }
  }
  if (visibleModeCount < 2) throw new Error(`[shot] 可见模式按钮不足，实际 ${visibleModeCount}`);

  const mapped = page.locator('#paneR [data-source-blocks]:not(.mv-edge)').first();
  if (!await mapped.count()) throw new Error('[shot] 缺少可交互映射元素: [data-source-blocks]');
  await mapped.focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(160);
  if (!await page.locator('[data-source-blocks].is-pinned').count()) {
    throw new Error('[shot] 键盘 Enter 后没有出现 pinned 状态: [data-source-blocks].is-pinned');
  }
  await page.keyboard.press('Escape');
  await page.waitForTimeout(80);
  if (await page.locator('.is-pinned').count()) throw new Error('[shot] Escape 未清除 pinned 状态');
  await mapped.click();
  await page.waitForTimeout(120);
  if (!await page.locator('[data-source-blocks].is-pinned').count()) throw new Error('[shot] 点击映射元素后没有出现 pinned 状态');
  const edgeFocus = await mapped.evaluate(el => {
    const flow = el.closest('[data-flow]');
    const active = [...document.querySelectorAll('.mv-edge-path.is-active')];
    return { active: active.length, outside: active.filter(path => path.closest('[data-flow]') !== flow).length };
  });
  if (!edgeFocus.active || edgeFocus.outside) {
    throw new Error(`[shot] 连线高亮越过当前 flow: ${JSON.stringify(edgeFocus)}`);
  }

  const sourceId = await mapped.evaluate(el => (el.getAttribute('data-source-blocks') || '').trim().split(/\s+/)[0]);
  const source = page.locator(`#paneL [data-block-id="${sourceId}"]`);
  await page.locator('[data-md2view-mode="l"]').click();
  await page.waitForTimeout(420);
  const revealHealth = await source.evaluate(el => {
    const pane = document.querySelector('#paneL');
    const paneRect = pane.getBoundingClientRect();
    const rect = el.getBoundingClientRect();
    return {
      pinned: el.classList.contains('is-pinned'),
      visible: rect.bottom > paneRect.top && rect.top < paneRect.bottom,
      paneWidth: paneRect.width,
      viewportWidth: window.innerWidth,
    };
  });
  if (!revealHealth.pinned || !revealHealth.visible || Math.abs(revealHealth.paneWidth - revealHealth.viewportWidth) > 2) {
    throw new Error(`[shot] 信息重组单栏 -> 原文预定位失败: ${JSON.stringify(revealHealth)}`);
  }
  await page.keyboard.press('Escape');
  await source.click();
  await page.waitForTimeout(100);
  await page.locator('[data-md2view-mode="r"]').click();
  await page.waitForTimeout(420);
  const reverseRevealHealth = await mapped.evaluate(el => {
    const pane = document.querySelector('#paneR');
    const paneRect = pane.getBoundingClientRect();
    const rect = el.getBoundingClientRect();
    return {
      pinned: el.classList.contains('is-pinned'),
      visible: rect.bottom > paneRect.top && rect.top < paneRect.bottom,
      paneWidth: paneRect.width,
      viewportWidth: window.innerWidth,
    };
  });
  if (!reverseRevealHealth.pinned || !reverseRevealHealth.visible || Math.abs(reverseRevealHealth.paneWidth - reverseRevealHealth.viewportWidth) > 2) {
    throw new Error(`[shot] 原文单栏 -> 信息重组预定位失败: ${JSON.stringify(reverseRevealHealth)}`);
  }
  await page.keyboard.press('Escape');
  const bothMode = page.locator('[data-md2view-mode="both"]');
  if (await bothMode.isVisible()) await bothMode.click();
  else await page.locator('[data-md2view-mode="r"]').click();
  await page.waitForTimeout(240);

  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    const body = document.body;
    return {
      docClient: doc.clientWidth,
      docScroll: doc.scrollWidth,
      bodyClient: body ? body.clientWidth : 0,
      bodyScroll: body ? body.scrollWidth : 0,
    };
  });
  if (overflow.docScroll > overflow.docClient + 1 || overflow.bodyScroll > overflow.bodyClient + 1) {
    throw new Error(`[shot] ${width}px 视口存在横向溢出: ${JSON.stringify(overflow)}`);
  }
  const internalOverflow = await page.$$eval('.pane,section.view,[data-flow]', elements => elements.map(el => ({
    name: el.id || el.getAttribute('data-layout') || el.className,
    client: el.clientWidth,
    scroll: el.scrollWidth,
  })).filter(item => item.client > 0 && item.scroll > item.client + 1));
  if (internalOverflow.length) throw new Error(`[shot] ${width}px 内部容器横向溢出: ${JSON.stringify(internalOverflow.slice(0, 4))}`);

  const semanticOverflow = await page.$$eval('.mv-node-title,.mv-node-detail,.mv-node-meta span,.mv-fact strong,.mv-fact span', elements => elements.map(el => ({
    text: (el.textContent || '').trim().slice(0, 28),
    className: el.className,
    client: el.clientWidth,
    scroll: el.scrollWidth,
  })).filter(item => item.client > 0 && item.scroll > item.client + 1));
  if (semanticOverflow.length) throw new Error(`[shot] ${width}px 语义文本溢出: ${JSON.stringify(semanticOverflow.slice(0, 4))}`);

  const factHealth = await page.$$eval('.mv-fact', facts => {
    const flows = [...document.querySelectorAll('[data-flow]')];
    const seen = new Set();
    const problems = [];
    facts.forEach(fact => {
      const id = fact.getAttribute('data-fact-id') || '';
      const source = (fact.getAttribute('data-source-blocks') || '').trim();
      const flow = fact.closest('[data-flow]');
      const scope = flow ? flows.indexOf(flow) : -1;
      const scopedId = `${scope}:${id}`;
      if (!id) problems.push({ reason: 'missing-id', text: (fact.textContent || '').trim().slice(0, 32) });
      if (!source) problems.push({ reason: 'missing-source', id });
      if (id && seen.has(scopedId)) problems.push({ reason: 'duplicate-id', id });
      if (id) seen.add(scopedId);
    });
    return { count: facts.length, problems };
  });
  if (factHealth.problems.length) throw new Error(`[shot] facts 合同失败: ${JSON.stringify(factHealth.problems.slice(0, 4))}`);

  const edgeCount = await assertLocator(page, '.mv-edge-path', '动态连线路径');
  const edgeHealth = await collectEdgeHealth(page);
  const broken = edgeHealth.filter(edge => {
    return !edge.d.trim() ||
      edge.numberCount < 4 ||
      !edge.finiteNumbers ||
      edge.lengthError ||
      !Number.isFinite(edge.totalLength) ||
      edge.totalLength <= 0 ||
      !Number.isFinite(edge.startGap) || edge.startGap > 3 ||
      !Number.isFinite(edge.endGap) || edge.endGap > 3 ||
      !edge.withinLayer ||
      edge.crossesNode;
  });
  if (broken.length) {
    throw new Error(`[shot] ${broken.length}/${edgeCount} 条连线路径无效: ${JSON.stringify(broken.slice(0, 3))}`);
  }
}

async function preparePage(page, html) {
  await page.goto('file://' + path.resolve(html));
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(350);
  await page.evaluate(() => document.querySelectorAll('section.view').forEach(s => s.classList.add('in')));
  await page.waitForTimeout(200);
}

(async () => {
  const cfg = parseArgs(process.argv.slice(2));
  fs.mkdirSync(cfg.outDir, { recursive: true });

  const browser = await chromium.launch();
  const failures = [];
  const warnings = [];

  try {
    for (const width of cfg.viewports) {
      const page = await browser.newPage({
        viewport: { width, height: cfg.height },
        deviceScaleFactor: 1.5,
      });
      const pageErrors = [];
      page.on('console', msg => {
        if (msg.type() === 'error') pageErrors.push(`console.error: ${msg.text()}`);
      });
      page.on('pageerror', err => pageErrors.push(`pageerror: ${err.message}`));

      try {
        await preparePage(page, cfg.html);
        if (cfg.assertions) await runAssertions(page, width);
        if (pageErrors.length) throw new Error(`[shot] 页面错误: ${pageErrors.join(' | ')}`);

        await page.screenshot({ path: path.join(cfg.outDir, `full-${width}.png`), fullPage: true });
        for (const sel of cfg.selectors) {
          const el = await page.$(sel);
          if (el) {
            await el.screenshot({ path: path.join(cfg.outDir, `${safeName(sel)}-${width}.png`) });
          } else {
            warnings.push(`[shot] ${width}px 未找到 ${sel}`);
          }
        }
      } catch (err) {
        failures.push(`${width}px: ${err && err.message || err}`);
        try {
          await page.screenshot({ path: path.join(cfg.outDir, `failure-${width}.png`), fullPage: true });
        } catch (_) {}
      } finally {
        await page.close();
      }
    }
  } finally {
    await browser.close();
  }

  for (const warning of warnings) console.warn(warning);
  if (failures.length) {
    console.error('[shot] 回归失败:');
    for (const failure of failures) console.error(' - ' + failure);
    process.exit(1);
  }

  const mode = cfg.assertions ? '截图 + smoke assertions 完成' : '截图完成（assertions 已关闭）';
  console.log(`[shot] ${mode} -> ${cfg.outDir} (${cfg.viewports.join(', ')})`);
})();
