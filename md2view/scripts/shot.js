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
const { execFileSync } = require('child_process');
const { createRequire } = require('module');

function loadPlaywright() {
  const moduleNames = ['@playwright/test', 'playwright'];
  const loaders = [require];
  const projectRoots = [process.cwd(), process.env.INIT_CWD, process.env.MD2VIEW_PLAYWRIGHT_ROOT]
    .filter(Boolean);
  for (const root of [...new Set(projectRoots)]) {
    loaders.push(createRequire(path.join(path.resolve(root), 'package.json')));
  }

  for (const loader of loaders) {
    for (const moduleName of moduleNames) {
      try {
        const loaded = loader(moduleName);
        if (loaded && loaded.chromium) return loaded.chromium;
      } catch (_) {}
    }
  }

  try {
    const globalRoot = execFileSync('npm', ['root', '-g'], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
    for (const moduleName of moduleNames) {
      try {
        const loaded = require(path.join(globalRoot, moduleName));
        if (loaded && loaded.chromium) return loaded.chromium;
      } catch (_) {}
    }
  } catch (_) {}

  console.error('[shot] 需要 playwright 与 Chromium。任选一种安装位置：');
  console.error('       当前目录：npm i -D playwright && npx playwright install chromium');
  console.error('       全局目录：npm i -g playwright && playwright install chromium');
  console.error('       其他项目：MD2VIEW_PLAYWRIGHT_ROOT=/abs/project python3 scripts/build_reader.py ...');
  process.exit(1);
}

const chromium = loadPlaywright();

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
  return page.$$eval('.mv-edge-path', paths => {
    const cssVisible = el => {
      if (typeof el.checkVisibility === 'function') {
        try {
          if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false;
        } catch (_) {}
      }
      for (let current = el; current; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) <= 0.05) return false;
      }
      return true;
    };
    const hasPaint = value => {
      const paint = String(value || '').trim().toLowerCase();
      return Boolean(paint) && paint !== 'none' && paint !== 'transparent' &&
        !/rgba\([^)]*,\s*0(?:\.0+)?\s*\)/.test(paint) &&
        !/\/\s*0(?:\.0+)?%?\s*\)/.test(paint);
    };
    return paths.map((pathEl, index) => {
    const d = pathEl.getAttribute('d') || '';
    const numbers = d.match(/-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?/gi) || [];
    const computed = getComputedStyle(pathEl);
    const visuallyVisible = cssVisible(pathEl) && hasPaint(computed.stroke) &&
      Number(computed.strokeOpacity || 1) > 0.05 && parseFloat(computed.strokeWidth || 0) > 0;
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
    let crossesFact = false;
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
      const facts = [...flow.querySelectorAll('.mv-fact')];
      for (let step = 1; step < 32 && (!crossesNode || !crossesFact); step += 1) {
        const sample = pathEl.getPointAtLength(totalLength * step / 32);
        const viewportPoint = new DOMPoint(sample.x, sample.y).matrixTransform(matrix);
        if (!crossesNode) crossesNode = otherNodes.some(node => {
          const rect = node.getBoundingClientRect();
          return viewportPoint.x > rect.left + 2 && viewportPoint.x < rect.right - 2 &&
            viewportPoint.y > rect.top + 2 && viewportPoint.y < rect.bottom - 2;
        });
        if (!crossesFact) crossesFact = facts.some(fact => {
          const rect = fact.getBoundingClientRect();
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
      crossesFact,
      visuallyVisible,
    };
    });
  });
}

async function collectEdgeLabelCollisions(page) {
  return page.$$eval('.mv-edge-label', labels => {
    const cssVisible = el => {
      if (typeof el.checkVisibility === 'function') {
        try {
          if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false;
        } catch (_) {}
      }
      for (let current = el; current; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) <= 0.05) return false;
      }
      return true;
    };
    const visible = labels.filter(label => {
      const style = getComputedStyle(label);
      const fill = String(style.fill || '').trim().toLowerCase();
      const painted = fill && fill !== 'none' && fill !== 'transparent' &&
        !/rgba\([^)]*,\s*0(?:\.0+)?\s*\)/.test(fill) &&
        !/\/\s*0(?:\.0+)?%?\s*\)/.test(fill) && Number(style.fillOpacity || 1) > 0.05;
      return (label.textContent || '').trim() && cssVisible(label) && painted &&
        label.getBoundingClientRect().width > 0;
    });
    const overlaps = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 &&
      Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2;
    const collisions = [];
    visible.forEach((label, index) => {
      const rect = label.getBoundingClientRect();
      for (let otherIndex = index + 1; otherIndex < visible.length; otherIndex += 1) {
        const other = visible[otherIndex];
        if (overlaps(rect, other.getBoundingClientRect())) {
          collisions.push({
            reason: 'label-label',
            labels: [(label.textContent || '').trim(), (other.textContent || '').trim()],
          });
        }
      }
      const flow = label.closest('[data-flow]');
      const content = flow && [...flow.querySelectorAll('.mv-node,.mv-fact')]
        .find(candidate => overlaps(rect, candidate.getBoundingClientRect()));
      if (content) {
        collisions.push({
          reason: content.classList.contains('mv-fact') ? 'label-fact' : 'label-node',
          label: (label.textContent || '').trim(),
          content: content.getAttribute('data-node-id') || content.getAttribute('data-fact-id') || '',
        });
      }
    });
    return collisions;
  });
}

async function collectLayoutProblems(page) {
  return page.$$eval('[data-flow]', flows => {
    const problems = [];
    const cssVisible = el => {
      if (typeof el.checkVisibility === 'function') {
        try {
          if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false;
        } catch (_) {}
      }
      for (let current = el; current; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) <= 0.05) return false;
      }
      const rect = el.getBoundingClientRect();
      return rect.width > 1 && rect.height > 1;
    };
    flows.forEach((flow, flowIndex) => {
      const flowName = flow.closest('section.view')?.id || `flow-${flowIndex + 1}`;
      const facts = [...flow.querySelectorAll('.mv-fact')].filter(el => el.offsetParent);
      const directFactGrids = [...flow.children].filter(el => el.classList.contains('mv-fact-grid') && el.offsetParent);
      if (facts.length && directFactGrids.length !== 1) {
        problems.push({ reason: 'fact-grid-scope', flow: flowName, facts: facts.length, directFactGrids: directFactGrids.length });
      }
      const style = getComputedStyle(flow);
      const usableWidth = flow.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
      directFactGrids.forEach(grid => {
        const gridStyle = getComputedStyle(grid);
        if (gridStyle.position === 'absolute' || gridStyle.position === 'fixed') {
          problems.push({ reason: 'fact-grid-out-of-flow', flow: flowName, position: gridStyle.position });
        }
        const ratio = usableWidth > 0 ? grid.getBoundingClientRect().width / usableWidth : 0;
        if (ratio < 0.85) problems.push({ reason: 'fact-grid-not-full-row', flow: flowName, ratio: Number(ratio.toFixed(2)) });
      });

      const allContent = [...flow.querySelectorAll('.mv-node,.mv-fact')];
      allContent.filter(el => !cssVisible(el)).forEach(el => {
        problems.push({
          reason: 'content-not-visible',
          flow: flowName,
          content: el.getAttribute('data-node-id') || el.getAttribute('data-fact-id') || '',
        });
      });
      const content = allContent.filter(cssVisible);
      const overlaps = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 3 &&
        Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 3;
      for (let index = 0; index < content.length; index += 1) {
        const first = content[index];
        const firstRect = first.getBoundingClientRect();
        for (let otherIndex = index + 1; otherIndex < content.length; otherIndex += 1) {
          const second = content[otherIndex];
          if (first.contains(second) || second.contains(first)) continue;
          if (!overlaps(firstRect, second.getBoundingClientRect())) continue;
          problems.push({
            reason: 'content-overlap',
            flow: flowName,
            first: first.getAttribute('data-node-id') || first.getAttribute('data-fact-id') || '',
            second: second.getAttribute('data-node-id') || second.getAttribute('data-fact-id') || '',
          });
        }
      }

      [...flow.querySelectorAll('.mv-node')].filter(el => el.offsetParent).forEach(node => {
        const current = node.getBoundingClientRect();
        const oldAlignSelf = node.style.alignSelf;
        const oldHeight = node.style.height;
        node.style.alignSelf = 'start';
        node.style.height = 'max-content';
        const naturalHeight = node.getBoundingClientRect().height;
        node.style.alignSelf = oldAlignSelf;
        node.style.height = oldHeight;
        const inflation = naturalHeight > 0 ? current.height / naturalHeight : 1;
        if (current.height - naturalHeight > 48 && inflation > 1.5) {
          problems.push({
            reason: 'stretched-node',
            flow: flowName,
            node: node.getAttribute('data-node-id') || '',
            height: Math.round(current.height),
            naturalHeight: Math.round(naturalHeight),
            inflation: Number(inflation.toFixed(2)),
          });
        }
        if (current.height > 160 && current.width > 0 && current.height / current.width > 0.85) {
          problems.push({
            reason: 'node-aspect',
            flow: flowName,
            node: node.getAttribute('data-node-id') || '',
            width: Math.round(current.width),
            height: Math.round(current.height),
          });
        }
      });
    });
    return problems;
  });
}

async function collectV3FamilyProblems(page) {
  return page.$$eval('section[data-v3-view]', views => {
    const problems = [];
    const visible = el => {
      if (!el) return false;
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return rect.width > 1 && rect.height > 1 && style.display !== 'none' &&
        style.visibility !== 'hidden' && Number(style.opacity || 1) > 0.05;
    };
    const overlaps = (a, b, tolerance = 3) =>
      Math.min(a.right, b.right) - Math.max(a.left, b.left) > tolerance &&
      Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > tolerance;

    views.forEach((view, viewIndex) => {
      const viewId = view.id || `view-${viewIndex + 1}`;
      const kind = view.dataset.diagramKind || '';
      const diagram = view.querySelector('.mv-diagram');
      if (!['architecture', 'flow', 'matrix', 'argument'].includes(kind)) {
        problems.push({ reason: 'unsupported-family-rendered', view: viewId, kind });
        return;
      }
      if (!visible(diagram)) problems.push({ reason: 'diagram-not-visible', view: viewId, kind });

      const primaries = [...view.querySelectorAll('[data-emphasis="primary"]')];
      if (primaries.length !== 1) {
        problems.push({ reason: 'primary-count', view: viewId, count: primaries.length });
      }
      const focalIds = (view.dataset.focalIds || '').trim().split(/\s+/).filter(Boolean);
      focalIds.forEach(focalId => {
        if (!view.querySelector(`[data-entity-id="${CSS.escape(focalId)}"],[data-fact-id="${CSS.escape(focalId)}"]`)) {
          problems.push({ reason: 'missing-focal', view: viewId, focalId });
        }
      });

      [...view.querySelectorAll('[data-source-blocks]')].forEach(mapped => {
        if (!(mapped.getAttribute('data-source-blocks') || '').trim()) {
          problems.push({ reason: 'empty-source-map', view: viewId, tag: mapped.tagName });
        }
        if (!(mapped.textContent || '').trim()) {
          problems.push({ reason: 'empty-mapped-content', view: viewId, tag: mapped.tagName });
        }
      });

      const peerBoxes = new Map();
      [...view.querySelectorAll('.mv-region')].forEach(region => {
        const parent = region.parentElement && region.parentElement.closest('.mv-region');
        const key = parent ? parent.dataset.regionId : '<root>';
        if (!peerBoxes.has(key)) peerBoxes.set(key, []);
        peerBoxes.get(key).push(region);
      });
      peerBoxes.forEach(regions => {
        regions.filter(visible).forEach((region, index) => {
          const rect = region.getBoundingClientRect();
          regions.slice(index + 1).filter(visible).forEach(other => {
            if (overlaps(rect, other.getBoundingClientRect())) {
              problems.push({
                reason: 'peer-region-overlap',
                view: viewId,
                first: region.dataset.regionId,
                second: other.dataset.regionId,
              });
            }
          });
        });
      });

      if (kind === 'architecture') {
        const structuralKinds = new Set(['contains', 'partOf', 'layerOf', 'instanceOf']);
        [...view.querySelectorAll('.mv-relation[data-relation-id]')].forEach(relation => {
          if (!structuralKinds.has(relation.dataset.kind)) return;
          if (relation.dataset.visual !== 'containment') {
            problems.push({ reason: 'structural-visual', view: viewId, relation: relation.dataset.relationId });
          }
          if (view.querySelector(`.mv-connector[data-relation-id="${CSS.escape(relation.dataset.relationId)}"],.mv-architecture-relation[data-relation-id="${CSS.escape(relation.dataset.relationId)}"]`)) {
            problems.push({ reason: 'structural-connector', view: viewId, relation: relation.dataset.relationId });
          }
          if (relation.dataset.kind === 'contains') {
            const subject = view.querySelector(`[data-owner-entity-id="${CSS.escape(relation.dataset.subject || '')}"]`);
            const object = view.querySelector(`[data-entity-id="${CSS.escape(relation.dataset.object || '')}"]`);
            if (!subject || !object || !subject.contains(object) || subject === object) {
              problems.push({ reason: 'contains-without-nesting', view: viewId, relation: relation.dataset.relationId });
            }
          }
        });
        [...view.querySelectorAll('.mv-architecture-relation')].forEach(relation => {
          if (!relation.dataset.visual || !visible(relation)) {
            problems.push({ reason: 'architecture-relation-not-readable', view: viewId, relation: relation.dataset.relationId });
          }
        });
        [...view.querySelectorAll('.mv-region--crosscut')].forEach(region => {
          const targets = (region.dataset.targetRegionIds || '').trim().split(/\s+/).filter(Boolean);
          if (!targets.length || !visible(region.querySelector('.mv-crosscut-targets'))) {
            problems.push({ reason: 'crosscut-without-targets', view: viewId, region: region.dataset.regionId });
          }
          targets.forEach(target => {
            if (!view.querySelector(`[data-region-id="${CSS.escape(target)}"]`)) {
              problems.push({ reason: 'crosscut-missing-target', view: viewId, region: region.dataset.regionId, target });
            }
          });
        });
      }

      if (kind === 'flow') {
        const connectors = [...view.querySelectorAll('.mv-connector[data-relation-id]')];
        if (!connectors.length) problems.push({ reason: 'flow-without-connector', view: viewId });
        connectors.forEach(connector => {
          if (connector.dataset.directed !== 'true' || !visible(connector)) {
            problems.push({ reason: 'flow-connector-invalid', view: viewId, relation: connector.dataset.relationId });
          }
          for (const endpoint of ['subject', 'object']) {
            const id = connector.dataset[endpoint];
            if (!id || !view.querySelector(`[data-entity-id="${CSS.escape(id)}"]`)) {
              problems.push({ reason: 'flow-endpoint-missing', view: viewId, relation: connector.dataset.relationId, endpoint });
            }
          }
        });
        const terminal = view.querySelector('[data-state-kind="terminal"],[data-state-kind="persistent"]');
        if (!terminal && view.dataset.readingKind !== 'cyclic') {
          problems.push({ reason: 'flow-without-terminal-or-cycle', view: viewId });
        }
      }

      if (kind === 'matrix') {
        const table = view.querySelector('table.mv-matrix');
        const options = table ? [...table.querySelectorAll('thead [data-entity-id]')] : [];
        if (!table || options.length < 2) {
          problems.push({ reason: 'matrix-shape', view: viewId, options: options.length });
        } else {
          [...table.querySelectorAll('tbody tr[data-fact-id]')].forEach(row => {
            const cells = row.querySelectorAll('td[data-target-id]');
            if (cells.length !== options.length) {
              problems.push({ reason: 'matrix-row-coverage', view: viewId, fact: row.dataset.factId, cells: cells.length, options: options.length });
            }
          });
        }
        if (view.querySelector('.mv-connector')) problems.push({ reason: 'matrix-has-flow-connector', view: viewId });
      }

      if (kind === 'argument') {
        const claim = view.querySelector('[data-argument-role="claim"]');
        const evidence = view.querySelector('[data-argument-role="evidence"],[data-argument-role="counterevidence"]');
        const relation = view.querySelector('.mv-argument-relation[data-kind]');
        if (!visible(claim) || !visible(evidence) || !visible(relation)) {
          problems.push({ reason: 'argument-shape', view: viewId });
        }
        if (view.querySelector('.mv-connector')) problems.push({ reason: 'argument-has-flow-connector', view: viewId });
      }
    });
    return problems;
  });
}

async function assertFactInteractions(page) {
  const factCase = await page.evaluate(() => {
    const splitIds = el => (el.getAttribute('data-source-blocks') || '').trim().split(/\s+/).filter(Boolean);
    const facts = [...document.querySelectorAll('#paneR .mv-fact[data-source-blocks]')];
    if (!facts.length) return null;

    const nodeSourceIds = new Set();
    document.querySelectorAll('#paneR .mv-node[data-source-blocks]').forEach(node => {
      splitIds(node).forEach(id => nodeSourceIds.add(id));
    });

    let factOnly = null;
    facts.forEach((fact, index) => {
      if (factOnly) return;
      const sourceId = splitIds(fact).find(id => !nodeSourceIds.has(id));
      if (sourceId) factOnly = { index, sourceId };
    });

    return {
      first: { index: 0, sourceId: splitIds(facts[0])[0] || null },
      factOnly,
    };
  });
  if (!factCase) return;

  const fact = page.locator('#paneR .mv-fact[data-source-blocks]').nth(factCase.first.index);
  await fact.focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(140);
  const factPinHealth = await fact.evaluate((el, sourceId) => {
    const source = sourceId ? document.querySelector(`#paneL [data-block-id="${CSS.escape(sourceId)}"]`) : null;
    return {
      factPinned: el.classList.contains('is-pinned'),
      sourceId,
      sourcePinned: source ? source.classList.contains('is-pinned') : false,
    };
  }, factCase.first.sourceId);
  if (!factPinHealth.factPinned || !factPinHealth.sourcePinned) {
    throw new Error(`[shot] fact 键盘 Enter 未精确 pin fact 与原文: ${JSON.stringify(factPinHealth)}`);
  }
  await page.keyboard.press('Escape');
  await page.waitForTimeout(80);
  if (await page.locator('.is-pinned').count()) throw new Error('[shot] fact Escape 未清除 pinned 状态');

  if (!factCase.factOnly) return;

  await page.locator('[data-md2view-mode="l"]').click();
  await page.waitForTimeout(180);
  await page.evaluate(sourceId => {
    document.querySelector(`#paneL [data-block-id="${CSS.escape(sourceId)}"]`)?.scrollIntoView({ block: 'center', inline: 'nearest' });
  }, factCase.factOnly.sourceId);
  await page.evaluate(sourceId => {
    const source = document.querySelector(`#paneL [data-block-id="${CSS.escape(sourceId)}"]`);
    if (!source) throw new Error(`missing source ${sourceId}`);
    source.click();
  }, factCase.factOnly.sourceId);
  await page.waitForTimeout(100);
  await page.locator('[data-md2view-mode="r"]').click();
  await page.waitForTimeout(420);

  const factOnly = page.locator('#paneR .mv-fact[data-source-blocks]').nth(factCase.factOnly.index);
  const factOnlyHealth = await factOnly.evaluate((el, sourceId) => {
    const pane = document.querySelector('#paneR');
    const paneRect = pane.getBoundingClientRect();
    const rect = el.getBoundingClientRect();
    const nodePinned = [...document.querySelectorAll('#paneR .mv-node.is-pinned')].some(node => {
      return (node.getAttribute('data-source-blocks') || '').trim().split(/\s+/).includes(sourceId);
    });
    return {
      sourceId,
      factPinned: el.classList.contains('is-pinned'),
      nodePinned,
      visible: rect.bottom > paneRect.top && rect.top < paneRect.bottom,
    };
  }, factCase.factOnly.sourceId);
  if (!factOnlyHealth.factPinned || factOnlyHealth.nodePinned || !factOnlyHealth.visible) {
    throw new Error(`[shot] fact-only 原文映射未精确落到 fact: ${JSON.stringify(factOnlyHealth)}`);
  }
  await page.keyboard.press('Escape');
  await page.waitForTimeout(80);
}

async function collectDensityMetrics(page, width) {
  const originalMode = await page.locator('[data-md2view-split]').getAttribute('data-layout') || 'both';
  await page.evaluate(() => window.setMode && window.setMode('r'));
  await page.waitForTimeout(180);
  const views = await page.$$eval('#paneR section.view', (sections, viewportWidth) => {
    const pane = document.querySelector('#paneR');
    const viewportHeight = pane ? pane.clientHeight : window.innerHeight;
    const round = (value, digits = 2) => Number(value.toFixed(digits));
    return sections.map((view, index) => {
      const isV3 = view.hasAttribute('data-v3-view');
      const flow = view.querySelector(isV3 ? '.mv-diagram' : '[data-flow]');
      const nodes = [...view.querySelectorAll(isV3 ? '[data-entity-id]' : '.mv-node')]
        .filter(el => el.offsetParent);
      const facts = [...view.querySelectorAll(isV3 ? '[data-fact-id]' : '.mv-fact')]
        .filter(el => el.offsetParent);
      const flowRect = flow && flow.getBoundingClientRect();
      const nonOverlappingFacts = facts.filter(fact => !fact.closest('.mv-node'));
      const contentArea = [...nodes, ...nonOverlappingFacts].reduce((sum, el) => {
        const rect = el.getBoundingClientRect();
        return sum + rect.width * rect.height;
      }, 0);
      const flowArea = flowRect ? flowRect.width * flowRect.height : 0;
      const units = nodes.length + facts.length;
      const viewHeight = view.getBoundingClientRect().height;
      return {
        width: viewportWidth,
        id: view.id || `view-${index + 1}`,
        kind: view.dataset.diagramKind || 'v2',
        nodes: nodes.length,
        facts: facts.length,
        units,
        viewHeight: Math.round(viewHeight),
        flowHeight: flowRect ? Math.round(flowRect.height) : 0,
        viewportRatio: viewportHeight ? round(viewHeight / viewportHeight) : 0,
        contentAreaRatio: flowArea ? round(contentArea / flowArea) : 0,
        unitsPerViewport: viewHeight ? round(units * viewportHeight / viewHeight, 1) : 0,
      };
    });
  }, width);
  await page.evaluate(mode => window.setMode && window.setMode(mode), originalMode);
  await page.waitForTimeout(120);
  return views;
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
    const node = el.closest('.mv-node');
    const nodeId = node && node.getAttribute('data-node-id');
    const active = [...document.querySelectorAll('.mv-edge-path.is-active')];
    const incident = flow && nodeId
      ? [...flow.querySelectorAll('.mv-edge-path')].filter(path => path.dataset.from === nodeId || path.dataset.to === nodeId).length
      : 0;
    return {
      active: active.length,
      incident,
      outside: active.filter(path => path.closest('[data-flow]') !== flow).length,
    };
  });
  if (edgeFocus.active !== edgeFocus.incident || edgeFocus.outside) {
    throw new Error(`[shot] 连线高亮范围错误: ${JSON.stringify(edgeFocus)}`);
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
  const reverseRevealHealth = await page.evaluate(() => {
    const pane = document.querySelector('#paneR');
    const paneRect = pane.getBoundingClientRect();
    const pinned = [...pane.querySelectorAll('[data-source-blocks].is-pinned')];
    const visiblePinned = pinned.filter(el => {
      const rect = el.getBoundingClientRect();
      return rect.height > 0 && rect.bottom > paneRect.top && rect.top < paneRect.bottom;
    });
    return {
      pinned: pinned.length > 0,
      visible: visiblePinned.length > 0,
      pinnedCount: pinned.length,
      visiblePinnedCount: visiblePinned.length,
      paneWidth: paneRect.width,
      viewportWidth: window.innerWidth,
    };
  });
  if (!reverseRevealHealth.pinned || !reverseRevealHealth.visible || Math.abs(reverseRevealHealth.paneWidth - reverseRevealHealth.viewportWidth) > 2) {
    throw new Error(`[shot] 原文单栏 -> 信息重组预定位失败: ${JSON.stringify(reverseRevealHealth)}`);
  }
  await page.keyboard.press('Escape');
  await assertFactInteractions(page);
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
  const internalOverflow = await page.$$eval('.pane,section.view,[data-flow],.mv-diagram', elements => elements.map(el => ({
    name: el.id || el.getAttribute('data-layout') || el.className,
    client: el.clientWidth,
    scroll: el.scrollWidth,
  })).filter(item => item.client > 0 && item.scroll > item.client + 1));
  if (internalOverflow.length) throw new Error(`[shot] ${width}px 内部容器横向溢出: ${JSON.stringify(internalOverflow.slice(0, 4))}`);

  const semanticOverflow = await page.$$eval('.mv-node-title,.mv-node-detail,.mv-node-meta span,.mv-fact strong,.mv-fact span,.mv-entity h3,.mv-entity p,.mv-matrix th,.mv-matrix td,.mv-architecture-relation', elements => elements.map(el => ({
    text: (el.textContent || '').trim().slice(0, 28),
    className: el.className,
    client: el.clientWidth,
    scroll: el.scrollWidth,
  })).filter(item => item.client > 0 && item.scroll > item.client + 1));
  if (semanticOverflow.length) throw new Error(`[shot] ${width}px 语义文本溢出: ${JSON.stringify(semanticOverflow.slice(0, 4))}`);

  const layoutProblems = await collectLayoutProblems(page);
  if (layoutProblems.length) throw new Error(`[shot] ${width}px 视觉密度布局失败: ${JSON.stringify(layoutProblems.slice(0, 4))}`);

  const familyProblems = await collectV3FamilyProblems(page);
  if (familyProblems.length) {
    throw new Error(`[shot] ${width}px v3 family 合同失败: ${JSON.stringify(familyProblems.slice(0, 6))}`);
  }

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

  const declaredEdgeCount = await page.locator('.mv-edge[data-from][data-to]').count();
  const edgeCount = await page.locator('.mv-edge-path').count();
  if (edgeCount !== declaredEdgeCount) {
    throw new Error(`[shot] 动态连线路径数量与声明不一致: 声明 ${declaredEdgeCount}，路径 ${edgeCount}`);
  }
  if (declaredEdgeCount) {
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
        edge.crossesNode ||
        edge.crossesFact ||
        !edge.visuallyVisible;
    });
    if (broken.length) {
      throw new Error(`[shot] ${broken.length}/${edgeCount} 条连线路径无效: ${JSON.stringify(broken.slice(0, 3))}`);
    }
    const labelCollisions = await collectEdgeLabelCollisions(page);
    if (labelCollisions.length) {
      throw new Error(`[shot] ${labelCollisions.length} 处连线标签碰撞: ${JSON.stringify(labelCollisions.slice(0, 4))}`);
    }
    const labelHealth = await page.evaluate(() => {
      const cssVisible = el => {
        if (typeof el.checkVisibility === 'function') {
          try {
            if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false;
          } catch (_) {}
        }
        for (let current = el; current; current = current.parentElement) {
          const style = getComputedStyle(current);
          if (style.display === 'none' || style.visibility !== 'visible' || Number(style.opacity) <= 0.05) return false;
        }
        return true;
      };
      const expected = [...document.querySelectorAll('.mv-edge[data-label]')]
        .filter(edge => (edge.getAttribute('data-label') || '').trim()).length;
      const labels = [...document.querySelectorAll('.mv-edge-label')]
        .filter(label => {
          const style = getComputedStyle(label);
          const fill = String(style.fill || '').trim().toLowerCase();
          const painted = fill && fill !== 'none' && fill !== 'transparent' &&
            !/rgba\([^)]*,\s*0(?:\.0+)?\s*\)/.test(fill) &&
            !/\/\s*0(?:\.0+)?%?\s*\)/.test(fill) && Number(style.fillOpacity || 1) > 0.05;
          return (label.textContent || '').trim() && cssVisible(label) && painted &&
            label.getBoundingClientRect().width > 0;
        });
      const badPlacement = labels.filter(label => Number(label.dataset.placementScore || 0) !== 0).map(label => ({
        text: (label.textContent || '').trim(),
        score: label.dataset.placementScore || 'missing',
      }));
      return { expected, visible: labels.length, badPlacement };
    });
    if (labelHealth.visible !== labelHealth.expected || labelHealth.badPlacement.length) {
      throw new Error(`[shot] 连线标签未完整安全落位: ${JSON.stringify(labelHealth)}`);
    }
  }
}

async function preparePage(page, html) {
  await page.goto('file://' + path.resolve(html));
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(350);
  await page.evaluate(() => document.querySelectorAll('section.view').forEach(s => s.classList.add('in')));
  await page.waitForTimeout(200);
}

async function prepareStableScreenshotState(page, semanticOnly = false) {
  await page.evaluate((semanticOnly) => {
    document.querySelectorAll('.is-pinned,.is-preview,.is-edge-focus').forEach(el => {
      el.classList.remove('is-pinned', 'is-preview', 'is-edge-focus');
    });
    const hint = document.querySelector('.hint');
    if (hint) {
      hint.classList.remove('show');
      hint.setAttribute('hidden', '');
    }
    const left = document.querySelector('#paneL');
    const right = document.querySelector('#paneR');
    if (left) left.scrollTop = 0;
    if (right) right.scrollTop = 0;

    let stableStyle = document.querySelector('#md2view-stable-shot-style');
    if (!stableStyle) {
      stableStyle = document.createElement('style');
      stableStyle.id = 'md2view-stable-shot-style';
      document.head.appendChild(stableStyle);
    }
    stableStyle.textContent = semanticOnly ? `
      html,body{overflow:visible!important;background:var(--surface-2)!important}
      header.bar,#paneL,.splitter,.hint{display:none!important}
      #split,#split.only-l,#split.only-r{display:block!important;height:auto!important;min-height:0!important}
      #paneR{display:block!important;height:auto!important;overflow:visible!important}
      #paneR .pane-tag{position:relative!important}
      #paneR .doc{max-width:1280px!important;margin:0 auto!important;padding-top:10px!important}
    ` : '';
  }, semanticOnly);
  await page.waitForTimeout(120);
}

(async () => {
  const cfg = parseArgs(process.argv.slice(2));
  fs.mkdirSync(cfg.outDir, { recursive: true });

  const browser = await chromium.launch();
  const failures = [];
  const warnings = [];
  const densityReports = [];

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
        if (cfg.assertions) {
          const metrics = await collectDensityMetrics(page, width);
          densityReports.push(...metrics);
          metrics.forEach(metric => {
            const ordinary = metric.nodes <= 8 && metric.facts <= 6;
            if (ordinary && metric.viewportRatio > 0.85) {
              warnings.push(`[shot] ${width}px ${metric.id} 超过 0.85 内容视口: ${metric.viewportRatio}`);
            }
            if (metric.units >= 4 && metric.contentAreaRatio < 0.28) {
              warnings.push(`[shot] ${width}px ${metric.id} 主体内容面积偏低: ${(metric.contentAreaRatio * 100).toFixed(0)}%`);
            }
            if (metric.units >= 4 && metric.contentAreaRatio < 0.22) {
              throw new Error(`[shot] ${width}px ${metric.id} 主体内容面积过低: ${(metric.contentAreaRatio * 100).toFixed(0)}%`);
            }
          });
        }

        await prepareStableScreenshotState(page, false);
        await page.screenshot({ path: path.join(cfg.outDir, `full-${width}.png`), fullPage: true });
        if (cfg.selectors.length) await prepareStableScreenshotState(page, true);
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

  for (const metric of densityReports) {
    console.log(`[shot] density ${metric.width}px ${metric.id}: ${metric.nodes}+${metric.facts} units, ` +
      `${metric.viewportRatio} viewport, ${(metric.contentAreaRatio * 100).toFixed(0)}% content-area, ` +
      `${metric.unitsPerViewport} units/viewport`);
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
