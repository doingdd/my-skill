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

async function screenshotElementWithFrame(page, element, outputPath, padding = 16) {
  const originalStyle = await element.getAttribute('style');
  const originalWidth = await element.evaluate(node => node.getBoundingClientRect().width);
  if (!(originalWidth > 0)) throw new Error('[shot] selector 截图区域为空');
  await element.evaluate((node, frame) => {
    node.style.setProperty('box-sizing', 'content-box', 'important');
    node.style.setProperty('width', `${frame.width}px`, 'important');
    node.style.setProperty('padding', `${frame.padding}px`, 'important');
    node.style.setProperty('margin-left', `${-frame.padding}px`, 'important');
  }, { width: originalWidth, padding });
  await page.waitForTimeout(40);
  try {
    await element.screenshot({ path: outputPath });
  } finally {
    await element.evaluate((node, style) => {
      if (style === null) node.removeAttribute('style');
      else node.setAttribute('style', style);
    }, originalStyle);
  }
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

async function collectFactCardStretchProblems(page) {
  return page.$$eval(
    [
      '.mv-flow-details > .mv-flow-detail-group',
      '.mv-flow-detail-facts > .mv-fact',
      '.mv-view-facts > .mv-fact',
    ].join(','),
    elements => {
      const visible = element => {
        if (!element || !element.offsetParent) return false;
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity || 1) > .05 && rect.width > 1 && rect.height > 1;
      };
      return elements.filter(visible).flatMap(element => {
        const current = element.getBoundingClientRect();
        const previousAlignSelf = element.style.alignSelf;
        const previousHeight = element.style.height;
        element.style.alignSelf = 'start';
        element.style.height = 'max-content';
        const naturalHeight = element.getBoundingClientRect().height;
        element.style.alignSelf = previousAlignSelf;
        element.style.height = previousHeight;
        const excessHeight = current.height - naturalHeight;
        const inflation = naturalHeight > 0 ? current.height / naturalHeight : 1;
        if (excessHeight <= 12 || inflation <= 1.15) return [];
        const view = element.closest('section[data-v3-view],section.view');
        const isGroup = element.classList.contains('mv-flow-detail-group');
        const isDetailFact = element.parentElement?.classList.contains('mv-flow-detail-facts');
        return [{
          reason: isGroup ? 'stretched-flow-detail-group' :
            isDetailFact ? 'stretched-flow-detail-fact' : 'stretched-view-fact',
          view: view?.id || '',
          target: isGroup ? element.dataset.flowDetailTarget || '' :
            element.dataset.factId || '',
          renderedHeight: Number(current.height.toFixed(2)),
          naturalHeight: Number(naturalHeight.toFixed(2)),
          excessHeight: Number(excessHeight.toFixed(2)),
          inflation: Number(inflation.toFixed(2)),
        }];
      });
    },
  );
}

async function collectFlowDetailDensityProblems(page) {
  return page.$$eval(
    'section[data-v3-view][data-diagram-kind="flow"]',
    views => {
      const limit = 1.5;
      const visible = element => {
        if (!element || !element.offsetParent) return false;
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity || 1) > .05 && rect.width > 1 && rect.height > 1;
      };
      const area = element => {
        const rect = element.getBoundingClientRect();
        return rect.width * rect.height;
      };
      return views.flatMap(view => {
        const details = view.querySelector('.mv-flow-details');
        const sequence = view.querySelector('.mv-flow-sequence');
        const branches = view.querySelector('.mv-flow-branches');
        if (!visible(details) || !visible(sequence)) return [];
        const detailArea = area(details);
        const mainArea = [sequence, branches].filter(visible)
          .reduce((sum, element) => sum + area(element), 0);
        const ratio = mainArea > 0 ? detailArea / mainArea : 0;
        if (ratio <= limit) return [];
        return [{
          reason: 'flow-detail-dominates-main',
          view: view.id || '',
          ratio: Number(ratio.toFixed(2)),
          limit,
          detailArea: Math.round(detailArea),
          mainArea: Math.round(mainArea),
          detailFacts: details.querySelectorAll('.mv-fact[data-fact-id],.mv-fact').length,
        }];
      });
    },
  );
}

async function collectArchitectureStructuralSkeletonProblems(page) {
  return page.$$eval(
    'section[data-v3-view][data-diagram-kind="architecture"]',
    views => {
      const problems = [];
      const splitTokens = value => String(value || '').trim().split(/\s+/).filter(Boolean);
      const unique = values => [...new Set(values)];
      const sorted = values => [...values].sort();
      const sameSet = (left, right) => {
        const leftSorted = sorted(left);
        const rightSorted = sorted(right);
        return leftSorted.length === rightSorted.length &&
          leftSorted.every((value, index) => value === rightSorted[index]);
      };
      const visible = element => {
        if (!element) return false;
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity || 1) > .05 && rect.width > 1 && rect.height > 1;
      };
      const rectOf = element => element.getBoundingClientRect();
      const overlaps = (a, b, tolerance = 3) =>
        Math.min(a.right, b.right) - Math.max(a.left, b.left) > tolerance &&
        Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > tolerance;
      const overflows = (inner, outer, tolerance = 2) =>
        inner.left < outer.left - tolerance || inner.right > outer.right + tolerance ||
        inner.top < outer.top - tolerance || inner.bottom > outer.bottom + tolerance;
      const center = rect => ({
        x: (rect.left + rect.right) / 2,
        y: (rect.top + rect.bottom) / 2,
      });
      const pointToRectDistance = (point, rect) => {
        const dx = Math.max(rect.left - point.x, 0, point.x - rect.right);
        const dy = Math.max(rect.top - point.y, 0, point.y - rect.bottom);
        return Math.hypot(dx, dy);
      };
      const rectDistance = (first, second) => {
        const dx = Math.max(first.left - second.right, second.left - first.right, 0);
        const dy = Math.max(first.top - second.bottom, second.top - first.bottom, 0);
        return Math.hypot(dx, dy);
      };
      const closeToMember = (segmentRect, memberRect) => {
        const segmentCenter = center(segmentRect);
        const memberCenter = center(memberRect);
        const aligned = (
          segmentCenter.x >= memberRect.left - 8 && segmentCenter.x <= memberRect.right + 8
        ) || (
          segmentCenter.y >= memberRect.top - 8 && segmentCenter.y <= memberRect.bottom + 8
        ) || Math.abs(segmentCenter.y - memberCenter.y) <= Math.max(10, memberRect.height * .38);
        return aligned && rectDistance(segmentRect, memberRect) <= 18;
      };
      const closeToRail = (segmentRect, railRect) =>
        rectDistance(segmentRect, railRect) <= 14 ||
        pointToRectDistance(center(segmentRect), railRect) <= 14;

      views.forEach((view, viewIndex) => {
        const viewId = view.id || `view-${viewIndex + 1}`;
        const diagram = view.querySelector('.mv-diagram--architecture,.mv-diagram');
        if (!diagram) return;
        const markers = [...view.querySelectorAll('.mv-relation[data-relation-id][data-kind][data-subject][data-object]')]
          .filter(marker => ['contains', 'partOf', 'layerOf', 'instanceOf'].includes(marker.dataset.kind || ''));
        const markerIds = markers.map(marker => marker.dataset.relationId).filter(Boolean);
        const markerDuplicates = unique(markerIds.filter((id, index) => markerIds.indexOf(id) !== index));
        if (markerDuplicates.length) {
          problems.push({
            reason: 'structural-marker-duplicate',
            view: viewId,
            duplicates: markerDuplicates,
          });
        }
        const presentationRefs = [...view.querySelectorAll(
          '.mv-structural-group[data-relation-id],.mv-structural-group [data-relation-id],' +
          '.mv-structural-spine[data-relation-id],.mv-structural-spine [data-relation-id]',
        )]
          .map(element => element.dataset.relationId).filter(Boolean);
        if (presentationRefs.length) {
          problems.push({
            reason: 'structural-presentation-uses-data-relation-id',
            view: viewId,
            relationIds: unique(presentationRefs),
          });
        }

        const entity = id => view.querySelector(`[data-entity-id="${CSS.escape(id)}"]`);
        const ownerRegion = id => view.querySelector(`.mv-region[data-owner-entity-id="${CSS.escape(id)}"]`);
        const footprint = id => ownerRegion(id) || entity(id);
        const directParentOwnerId = id => {
          const region = ownerRegion(id) || entity(id)?.closest('.mv-region');
          const parent = region?.parentElement?.closest('.mv-region[data-owner-entity-id]');
          return parent?.dataset.ownerEntityId || '';
        };
        const groupRelations = (kind, minimum) => {
          const groups = new Map();
          markers.filter(marker => marker.dataset.kind === kind).forEach(marker => {
            const subjectId = marker.dataset.subject || '';
            const objectId = marker.dataset.object || '';
            const parentOwnerId = directParentOwnerId(subjectId);
            if (!subjectId || !objectId || parentOwnerId !== objectId) return;
            const key = `${kind}\u0001${objectId}`;
            if (!groups.has(key)) {
              groups.set(key, {
                kind,
                family: kind === 'instanceOf' ? 'instance' : 'layer',
                parentId: objectId,
                relations: [],
              });
            }
            groups.get(key).relations.push({
              id: marker.dataset.relationId || '',
              subjectId,
              objectId,
            });
          });
          return [...groups.values()].filter(group => group.relations.length >= minimum);
        };
        const expectedFamilies = [
          ...groupRelations('instanceOf', 2),
          ...groupRelations('layerOf', 3),
        ];

        const containsGroups = new Map();
        markers.filter(marker => marker.dataset.kind === 'contains').forEach(marker => {
          const subjectId = marker.dataset.subject || '';
          const objectId = marker.dataset.object || '';
          if (!subjectId || !objectId || directParentOwnerId(objectId) !== subjectId) return;
          if (!containsGroups.has(subjectId)) containsGroups.set(subjectId, []);
          containsGroups.get(subjectId).push(objectId);
        });
        containsGroups.forEach((memberIds, parentId) => {
          const layerLike = memberIds.filter(id => {
            const label = (entity(id)?.textContent || '').trim();
            return /(^|\b)L\d+\b|第[一二三四五六七八九十]+层|层级|layer/i.test(label);
          });
          if (layerLike.length >= 3) {
            problems.push({
              reason: 'architecture-layer-family-encoded-as-contains',
              view: viewId,
              parentId,
              memberIds: layerLike,
            });
          }
        });

        expectedFamilies.forEach(expected => {
          const relationIds = expected.relations.map(relation => relation.id).filter(Boolean);
          const memberIds = expected.relations.map(relation => relation.subjectId);
          const commonRegion = ownerRegion(expected.parentId) ||
            footprint(memberIds[0])?.parentElement?.closest('.mv-region');
          const commonRect = commonRegion ? rectOf(commonRegion) : rectOf(diagram);
          const groups = [...view.querySelectorAll(
            `.mv-structural-group[data-structural-family="${CSS.escape(expected.family)}"]` +
            `[data-structural-parent-id="${CSS.escape(expected.parentId)}"]`,
          )].filter(visible);
          if (groups.length !== 1) {
            problems.push({
              reason: groups.length ? 'structural-group-duplicate' : 'structural-group-missing',
              view: viewId,
              family: expected.family,
              parentId: expected.parentId,
              expectedRelations: relationIds,
              visibleGroups: groups.length,
            });
            return;
          }
          const group = groups[0];
          const spines = [...group.querySelectorAll('.mv-structural-spine')].filter(visible);
          if (spines.length !== 1) {
            problems.push({
              reason: spines.length ? 'structural-spine-duplicate' : 'structural-spine-missing',
              view: viewId,
              family: expected.family,
              parentId: expected.parentId,
              expectedRelations: relationIds,
              visibleSpines: spines.length,
            });
          }
          const spine = spines[0] || group;
          const refCarriers = [group, ...spines];
          refCarriers.forEach((carrier, carrierIndex) => {
            const declaredRelations = splitTokens(carrier.dataset.structuralRelationIds);
            const declaredMembers = splitTokens(carrier.dataset.structuralMemberIds);
            const declaredKind = carrier.dataset.structuralMemberKind || '';
            const declaredCount = Number(carrier.dataset.structuralMemberCount || NaN);
            if (sameSet(declaredRelations, relationIds) && sameSet(declaredMembers, memberIds) &&
                declaredKind === expected.kind && declaredCount === memberIds.length) return;
            problems.push({
              reason: 'structural-spine-ref-mismatch',
              view: viewId,
              family: expected.family,
              parentId: expected.parentId,
              carrier: carrierIndex === 0 ? 'group' : 'spine',
              expectedRelations: relationIds,
              declaredRelations,
              expectedMembers: memberIds,
              declaredMembers,
              expectedKind: expected.kind,
              declaredKind,
              expectedCount: memberIds.length,
              declaredCount,
            });
          });
          const groupRect = rectOf(group);
          const spineRect = rectOf(spine);
          if (groupRect.width <= 2 || groupRect.height <= 2 || overflows(groupRect, rectOf(diagram), 2)) {
            problems.push({
              reason: 'structural-group-geometry',
              view: viewId,
              family: expected.family,
              parentId: expected.parentId,
              width: Number(groupRect.width.toFixed(2)),
              height: Number(groupRect.height.toFixed(2)),
            });
          }
          if (spineRect.width <= 2 || spineRect.height <= 2 || overflows(spineRect, rectOf(diagram), 2)) {
            problems.push({
              reason: 'structural-spine-geometry',
              view: viewId,
              family: expected.family,
              parentId: expected.parentId,
              width: Number(spineRect.width.toFixed(2)),
              height: Number(spineRect.height.toFixed(2)),
            });
          }
          const railCandidates = [...group.querySelectorAll('.mv-structural-spine-rail')].filter(visible);
          const rail = railCandidates[0];
          const railRect = rail ? rectOf(rail) : null;
          if (railCandidates.length !== 1 || !railRect || Math.max(railRect.width, railRect.height) < 24) {
            problems.push({
              reason: railCandidates.length ? 'structural-spine-rail-duplicate' : 'structural-spine-rail-missing',
              view: viewId,
              family: expected.family,
              parentId: expected.parentId,
              rails: railCandidates.length,
            });
          }
          const memberRects = memberIds.map(id => ({ id, element: footprint(id), rect: footprint(id) ? rectOf(footprint(id)) : null }));
          memberRects.forEach(member => {
            if (!visible(member.element)) {
              problems.push({
                reason: 'structural-member-missing',
                view: viewId,
                family: expected.family,
                parentId: expected.parentId,
                memberId: member.id,
              });
              return;
            }
            if (overflows(member.rect, commonRect, 2)) {
              problems.push({
                reason: 'structural-member-overflow',
                view: viewId,
                family: expected.family,
                parentId: expected.parentId,
                memberId: member.id,
              });
            }
          });
          memberRects.forEach((member, index) => {
            if (!member.rect) return;
            memberRects.slice(index + 1).forEach(other => {
              if (other.rect && overlaps(member.rect, other.rect, 2)) {
                problems.push({
                  reason: 'structural-member-overlap',
                  view: viewId,
                  family: expected.family,
                  parentId: expected.parentId,
                  first: member.id,
                  second: other.id,
                });
              }
            });
          });
          expected.relations.forEach(relation => {
            const relationIdOf = segment =>
              segment.dataset.structuralRelationId || segment.dataset.structuralRelationRef || '';
            const segments = [...group.querySelectorAll('.mv-structural-spine-segment')]
              .filter(segment => relationIdOf(segment) === relation.id &&
                segment.dataset.structuralMemberId === relation.subjectId)
              .filter(visible);
            const memberRect = memberRects.find(member => member.id === relation.subjectId)?.rect;
            if (segments.length !== 1 || !memberRect || !railRect) {
              problems.push({
                reason: 'structural-spine-segment-ref-mismatch',
                view: viewId,
                family: expected.family,
                parentId: expected.parentId,
                relationId: relation.id,
                memberId: relation.subjectId,
                segments: segments.length,
              });
              return;
            }
            const segmentRect = rectOf(segments[0]);
            if (Math.max(segmentRect.width, segmentRect.height) < 10 ||
                !closeToRail(segmentRect, railRect) || !closeToMember(segmentRect, memberRect)) {
              problems.push({
                reason: 'structural-spine-segment-geometry',
                view: viewId,
                family: expected.family,
                parentId: expected.parentId,
                relationId: relation.id,
                memberId: relation.subjectId,
                width: Number(segmentRect.width.toFixed(2)),
                height: Number(segmentRect.height.toFixed(2)),
              });
            }
          });
          if (!railRect || memberRects.some(member => !member.rect)) return;
          const centers = memberRects.map(member => ({ id: member.id, ...center(member.rect) }));
          const minY = Math.min(...centers.map(item => item.y));
          const maxY = Math.max(...centers.map(item => item.y));
          const minX = Math.min(...centers.map(item => item.x));
          const maxX = Math.max(...centers.map(item => item.x));
          const narrow = commonRect.width < 640;
          const railCoversMembers = railRect.top <= minY + 4 && railRect.bottom >= maxY - 4;
          const groupColumnCount = getComputedStyle(group).display.includes('grid')
            ? getComputedStyle(group).gridTemplateColumns.split(/\s+/).filter(value => value && value !== 'none').length
            : 0;
          if (expected.family === 'layer') {
            const ordered = centers.every((item, index) => index === 0 || item.y > centers[index - 1].y + 4);
            const singleColumn = maxX - minX <= Math.max(90, commonRect.width * .18);
            const twoColumnGroup = groupColumnCount === 2;
            if (!ordered || !singleColumn || !twoColumnGroup || !railCoversMembers || railRect.height < maxY - minY - 4) {
              problems.push({
                reason: 'structural-layer-rail-geometry',
                view: viewId,
                parentId: expected.parentId,
                ordered,
                singleColumn,
                twoColumnGroup,
                railCoversMembers,
                memberSpreadX: Number((maxX - minX).toFixed(2)),
              });
            }
          } else if (expected.family === 'instance') {
            const multiColumn = maxX - minX >= Math.min(160, commonRect.width * .22);
            const groupHasMemberColumns = groupColumnCount >= Math.min(memberIds.length, 2);
            if (!narrow && (!multiColumn || !groupHasMemberColumns ||
                railRect.width < maxX - minX - 4 || railRect.width <= railRect.height * 3)) {
              problems.push({
                reason: 'structural-instance-wide-not-multicolumn',
                view: viewId,
                parentId: expected.parentId,
                memberSpreadX: Number((maxX - minX).toFixed(2)),
                commonWidth: Number(commonRect.width.toFixed(2)),
                groupColumns: groupColumnCount,
              });
            }
            if (narrow && (groupColumnCount !== 2 || !railCoversMembers || railRect.height < maxY - minY - 4)) {
              problems.push({
                reason: 'structural-instance-narrow-rail-geometry',
                view: viewId,
                parentId: expected.parentId,
                groupColumns: groupColumnCount,
                railCoversMembers,
              });
            }
          }
        });
      });
      return problems;
    },
  );
}

async function collectFlowMainPathProblems(page) {
  return page.$$eval(
    'section[data-v3-view][data-diagram-kind="flow"] .mv-flow-sequence',
    sequences => {
      const problems = [];
      const visible = element => {
        if (!element) return false;
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
          Number(style.opacity || 1) > .05 && rect.width > 1 && rect.height > 1;
      };
      const outside = (rect, bounds, tolerance = 1) =>
        rect.left < bounds.left - tolerance || rect.right > bounds.right + tolerance ||
        rect.top < bounds.top - tolerance || rect.bottom > bounds.bottom + tolerance;
      const gridNumber = (element, property) =>
        Number.parseInt(getComputedStyle(element)[property], 10) || 0;

      sequences.filter(visible).forEach(sequence => {
        const view = sequence.closest('section[data-v3-view]');
        const diagram = sequence.closest('.mv-diagram');
        const viewId = view?.id || 'flow';
        const sequenceRect = sequence.getBoundingClientRect();
        const diagramRect = diagram?.getBoundingClientRect() || sequenceRect;
        if (sequence.scrollWidth > sequence.clientWidth + 1) {
          problems.push({
            reason: 'flow-main-path-overflow', view: viewId,
            orientation: sequence.dataset.flowOrientation || '',
            clientWidth: sequence.clientWidth,
            scrollWidth: sequence.scrollWidth,
          });
        }
        [...sequence.children].filter(visible).forEach((child, index) => {
          const childRect = child.getBoundingClientRect();
          const outsideSequence = outside(childRect, sequenceRect);
          const outsideDiagram = outside(childRect, diagramRect);
          if (!outsideSequence && !outsideDiagram) return;
          problems.push({
            reason: 'flow-main-path-clipped', view: viewId, index,
            child: child.className || child.tagName,
            orientation: sequence.dataset.flowOrientation || '',
            outsideSequence, outsideDiagram,
            childRect: {
              left: Number(childRect.left.toFixed(1)),
              right: Number(childRect.right.toFixed(1)),
              top: Number(childRect.top.toFixed(1)),
              bottom: Number(childRect.bottom.toFixed(1)),
            },
            sequenceRect: {
              left: Number(sequenceRect.left.toFixed(1)),
              right: Number(sequenceRect.right.toFixed(1)),
              top: Number(sequenceRect.top.toFixed(1)),
              bottom: Number(sequenceRect.bottom.toFixed(1)),
            },
          });
        });
        if (sequence.dataset.flowOrientation === 'serpentine') {
          const perRow = Number(sequence.dataset.flowPerRow || 0);
          const children = [...sequence.children];
          const steps = children.filter(child => child.classList.contains('mv-flow-step'));
          const connectors = children.filter(child => child.classList.contains('mv-connector'));
          const issues = [];
          if (!Number.isInteger(perRow) || perRow < 2 || perRow > 4) {
            issues.push(`invalid-per-row:${perRow}`);
          }
          if (children.length !== steps.length * 2 - 1 || connectors.length !== steps.length - 1) {
            issues.push(`invalid-flat-sequence:${steps.length}/${connectors.length}/${children.length}`);
          }
          children.forEach((child, index) => {
            const expectedStep = index % 2 === 0;
            if (child.classList.contains(expectedStep ? 'mv-flow-step' : 'mv-connector')) return;
            issues.push(`dom-order:${index}`);
          });
          const expectedOrders = steps.map((_, index) => String(index + 1).padStart(2, '0'));
          const actualOrders = steps.map(step => step.dataset.flowOrder || '');
          if (new Set(actualOrders).size !== steps.length ||
              actualOrders.some((order, index) => order !== expectedOrders[index])) {
            issues.push('step-order');
          }
          const terminals = steps.filter(step => step.dataset.flowTerminal === 'true');
          if (terminals.length !== 1 || terminals[0] !== steps[steps.length - 1]) {
            issues.push(`terminal:${terminals.length}`);
          }
          if (perRow >= 2) {
            const normalizedSlot = index => {
              const group = Math.floor(index / perRow);
              const position = index % perRow;
              const groupSize = Math.min(perRow, steps.length - group * perRow);
              if (groupSize <= 1) return group % 2 === 0 ? 0 : perRow - 1;
              const progress = position / (groupSize - 1);
              return (group % 2 === 0 ? progress : 1 - progress) * (perRow - 1);
            };
            const integerSlot = slot => Math.abs(slot - Math.round(slot)) < .01;
            const connectorArea = (sourceSlot, targetSlot) => {
              const left = Math.min(sourceSlot, targetSlot);
              const right = Math.max(sourceSlot, targetSlot);
              return {
                start: integerSlot(left) ? Math.round(left) * 2 + 2 : Math.round(left * 2 + 1),
                end: integerSlot(right) ? Math.round(right) * 2 + 1 : Math.round(right * 2 + 2),
              };
            };
            steps.forEach((step, index) => {
              const group = Math.floor(index / perRow);
              const slot = normalizedSlot(index);
              const expectedRow = group * 2 + 1;
              const expectedColumn = integerSlot(slot) ? Math.round(slot) * 2 + 1 : Math.floor(slot) * 2 + 1;
              const expectedEnd = integerSlot(slot) ? 0 : expectedColumn + 3;
              if (Number(step.dataset.flowGridIndex) !== index ||
                  Number(step.dataset.flowGridGroup) !== group ||
                  Math.abs(Number(step.dataset.flowGridSlot) - slot) > .02 ||
                  gridNumber(step, 'gridRowStart') !== expectedRow ||
                  gridNumber(step, 'gridColumnStart') !== expectedColumn ||
                  gridNumber(step, 'gridColumnEnd') !== expectedEnd ||
                  (!integerSlot(slot) && getComputedStyle(step).justifySelf !== 'center')) {
                issues.push(`step-grid:${index}`);
              }
            });
            const lastGroup = Math.floor((steps.length - 1) / perRow);
            const lastGroupSteps = steps.filter((_, index) => Math.floor(index / perRow) === lastGroup);
            if (lastGroupSteps.length > 1) {
              const firstRow = steps.slice(0, Math.min(perRow, steps.length)).map(step => step.getBoundingClientRect());
              const lastRow = lastGroupSteps.map(step => step.getBoundingClientRect());
              const anchorLeft = Math.min(...firstRow.map(rect => rect.left));
              const anchorRight = Math.max(...firstRow.map(rect => rect.right));
              const lastLeft = Math.min(...lastRow.map(rect => rect.left));
              const lastRight = Math.max(...lastRow.map(rect => rect.right));
              if (Math.abs(anchorLeft - lastLeft) > 2 || Math.abs(anchorRight - lastRight) > 2) {
                issues.push('partial-row-anchors');
              }
            }
            connectors.forEach((connector, index) => {
              const sourceGroup = Math.floor(index / perRow);
              const targetGroup = Math.floor((index + 1) / perRow);
              const sourceSlot = normalizedSlot(index);
              const targetSlot = normalizedSlot(index + 1);
              const down = sourceGroup !== targetGroup;
              const direction = down ? 'down' : sourceGroup % 2 === 0 ? 'forward' : 'reverse';
              const expectedRow = down ? sourceGroup * 2 + 2 : sourceGroup * 2 + 1;
              const area = down ? { start: Math.round(sourceSlot) * 2 + 1, end: 0 } : connectorArea(sourceSlot, targetSlot);
              if (Number(connector.dataset.flowGridIndex) !== index ||
                  Number(connector.dataset.flowGridGroup) !== sourceGroup ||
                  connector.dataset.flowGridDirection !== direction ||
                  gridNumber(connector, 'gridRowStart') !== expectedRow ||
                  gridNumber(connector, 'gridColumnStart') !== area.start ||
                  gridNumber(connector, 'gridColumnEnd') !== area.end) {
                issues.push(`connector-grid:${index}:${direction}`);
              }
              const sourceRect = steps[index]?.getBoundingClientRect();
              const targetRect = steps[index + 1]?.getBoundingClientRect();
              const connectorRect = connector.getBoundingClientRect();
              if (!sourceRect || !targetRect) return;
              if (down) {
                const aligned = Math.abs((sourceRect.left + sourceRect.right) / 2 -
                  (targetRect.left + targetRect.right) / 2) <= 2;
                const between = connectorRect.top >= sourceRect.bottom - 1 &&
                  connectorRect.bottom <= targetRect.top + 1;
                const marker = connector.querySelector(':scope > span');
                const markerRect = marker?.getBoundingClientRect();
                const line = getComputedStyle(connector, '::before');
                const arrow = getComputedStyle(connector, '::after');
                const markerVisible = markerRect && markerRect.width >= 13 && markerRect.height >= 13 &&
                  line.content !== 'none' && parseFloat(line.width) >= 2.5 && arrow.content !== 'none';
                if (!aligned || !between || !markerVisible) issues.push(`u-turn:${index}`);
              } else {
                const left = sourceRect.left < targetRect.left ? sourceRect : targetRect;
                const right = left === sourceRect ? targetRect : sourceRect;
                const lineRect = connector.querySelector(':scope > span')?.getBoundingClientRect() || connectorRect;
                const bridges = lineRect.left <= left.right + 1 && lineRect.right >= right.left - 1;
                const sameRow = Math.abs(sourceRect.top - targetRect.top) <= 1;
                if (!bridges || !sameRow) issues.push(`same-row:${index}:${direction}`);
                if (direction === 'reverse') {
                  const marker = getComputedStyle(steps[index + 1], '::after');
                  if (marker.content === 'none' || parseFloat(marker.width) < 7) {
                    issues.push(`reverse-arrow:${index}`);
                  }
                }
              }
            });
          }
          if (issues.length) {
            problems.push({
              reason: 'flow-serpentine-continuity', view: viewId,
              perRow, issues: [...new Set(issues)],
            });
          }
        }
      });
      return problems;
    },
  );
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

      const declaredGroups = [
        ['entity', 'declaredEntityIds', '[data-entity-id]', 'entityId', true],
        ['relation', 'declaredRelationIds', '[data-relation-id]', 'relationId', false],
        ['fact', 'declaredFactIds', '[data-fact-id]', 'factId', true],
      ];
      declaredGroups.forEach(([group, declaredKey, selector, actualKey, requireVisible]) => {
        const expected = (view.dataset[declaredKey] || '').trim().split(/\s+/).filter(Boolean);
        const elements = [...view.querySelectorAll(selector)];
        const actual = elements.map(element => element.dataset[actualKey]).filter(Boolean);
        const missing = expected.filter(id => !actual.includes(id));
        const extra = actual.filter(id => !expected.includes(id));
        const duplicates = [...new Set(actual.filter((id, index) => actual.indexOf(id) !== index))];
        if (missing.length || extra.length || duplicates.length) {
          problems.push({
            reason: 'declared-item-mismatch', view: viewId, group,
            missing, extra, duplicates,
          });
        }
        elements.forEach(element => {
          const containmentMarker = group === 'relation' && element.dataset.visual === 'containment';
          if ((requireVisible || !containmentMarker) && !visible(element)) {
            problems.push({
              reason: 'declared-item-not-visible', view: viewId, group,
              id: element.dataset[actualKey] || '',
            });
          }
        });
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
        const visibleRegions = regions.filter(visible);
        visibleRegions.forEach((region, index) => {
          const rect = region.getBoundingClientRect();
          visibleRegions.slice(index + 1).forEach(other => {
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
        const crossBoundaryRouteFamilies = new Set([
          'entry', 'output', 'support', 'dependency',
          'observation', 'crosscut', 'constraint',
        ]);
        const hasSemanticOwner = container => [...container.children]
          .some(child => child.classList.contains('mv-region-owner'));
        const closestSemanticContainer = element => {
          let container = element && element.closest('.mv-region--container');
          while (container && !hasSemanticOwner(container)) {
            container = container.parentElement && container.parentElement.closest('.mv-region--container');
          }
          return container;
        };
        const semanticContainerChain = element => {
          const chain = [];
          let container = closestSemanticContainer(element);
          while (container) {
            chain.push(container);
            container = closestSemanticContainer(container.parentElement);
          }
          return chain;
        };
        const closestCommonSemanticContainer = (first, second) => {
          const secondAncestors = new Set(semanticContainerChain(second));
          return semanticContainerChain(first)
            .find(container => secondAncestors.has(container)) || null;
        };
        const semanticFootprint = entity => {
          if (!entity) return entity;
          const ownedRegion = entity.classList.contains('mv-region-owner') ?
            entity.closest('.mv-region[data-owner-entity-id]') : null;
          if (ownedRegion && ownedRegion.dataset.ownerEntityId === entity.dataset.entityId) {
            return ownedRegion;
          }
          const cluster = entity.closest('.mv-entity-cluster[data-cluster-entity-id]');
          return cluster && cluster.dataset.clusterEntityId === entity.dataset.entityId ?
            cluster : entity;
        };
        const isBoundaryPortEndpoint = entity => entity && (
          entity.classList.contains('mv-region-owner')
        );
        const requiresBoundaryPortRoute = (subject, object, routeFamily) => {
          const entry = routeFamily === 'entry' &&
            subject.dataset.boundary === 'external' &&
            object.dataset.boundary !== 'external';
          const output = routeFamily === 'output' &&
            object.dataset.boundary === 'external' &&
            subject.dataset.boundary !== 'external';
          return (entry || output) &&
            (isBoundaryPortEndpoint(subject) || isBoundaryPortEndpoint(object));
        };
        const diagramRect = diagram.getBoundingClientRect();
        [...diagram.querySelectorAll(
          '.mv-region--container[data-boundary-orientation="compact"]' +
          '[data-boundary-layout="staged"]',
        )].filter(visible).forEach(root => {
          const rootRect = root.getBoundingClientRect();
          const directRegions = [...root.children]
            .filter(child => child.classList?.contains('mv-region') && visible(child));
          const requiredFullWidth = directRegions.filter(region =>
            region.dataset.role === 'main' ||
            (region.dataset.boundaryFlow === 'input' &&
              Number(root.dataset.boundaryInputCount || 0) === 1) ||
            (region.dataset.boundaryFlow === 'output' &&
              Number(root.dataset.boundaryOutputCount || 0) === 1));
          requiredFullWidth.forEach(region => {
            const rect = region.getBoundingClientRect();
            const widthRatio = rootRect.width > 0 ? rect.width / rootRect.width : 0;
            if (widthRatio < 0.9 || Math.abs(rect.left - rootRect.left) > 4) {
              problems.push({
                reason: 'architecture-compact-stage-not-full-width', view: viewId,
                region: region.dataset.regionId || '',
                boundaryFlow: region.dataset.boundaryFlow || '',
                widthRatio: Number(widthRatio.toFixed(3)),
                leftOffset: Number((rect.left - rootRect.left).toFixed(2)),
              });
            }
          });
        });
        const architectureText = [...diagram.querySelectorAll('h3,p,strong,span,small,th,td,code')]
          .filter(element => visible(element) && (element.textContent || '').trim() &&
            !element.closest('.mv-architecture-label-layer'));
        [...view.querySelectorAll('.mv-diagram--architecture .mv-entity[data-entity-id]')]
          .filter(visible).forEach(entity => {
          const current = entity.getBoundingClientRect();
          const previousAlignSelf = entity.style.alignSelf;
          const previousHeight = entity.style.height;
          entity.style.alignSelf = 'start';
          entity.style.height = 'max-content';
          const naturalHeight = entity.getBoundingClientRect().height;
          entity.style.alignSelf = previousAlignSelf;
          entity.style.height = previousHeight;
          const inflation = naturalHeight > 0 ? current.height / naturalHeight : 1;
          if (current.height - naturalHeight > 48 && inflation > 1.5) {
            problems.push({
              reason: 'architecture-stretched-entity', view: viewId,
              entity: entity.dataset.entityId || '',
              height: Number(current.height.toFixed(2)),
              naturalHeight: Number(naturalHeight.toFixed(2)),
              inflation: Number(inflation.toFixed(2)),
            });
          }
        });
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
          if (relation.closest('.mv-architecture-relations') || !relation.closest('[data-architecture-overlay]')) {
            problems.push({ reason: 'architecture-relation-index-only', view: viewId, relation: relation.dataset.relationId });
          }
          if (relation.dataset.layoutState !== 'drawn' ||
              relation.dataset.placementState !== 'placed') {
            problems.push({
              reason: 'architecture-relation-not-placed', view: viewId,
              relation: relation.dataset.relationId,
              layout: relation.dataset.layoutState || '',
              placement: relation.dataset.placementState || '',
            });
          }
          const relationRect = relation.getBoundingClientRect();
          const outOfBounds = relationRect.left < diagramRect.left + 7 ||
            relationRect.right > diagramRect.right - 7 ||
            relationRect.top < diagramRect.top + 7 ||
            relationRect.bottom > diagramRect.bottom - 7;
          if (outOfBounds) {
            problems.push({
              reason: 'architecture-relation-label-outside', view: viewId,
              relation: relation.dataset.relationId,
            });
          }
          const coveredText = architectureText
            .filter(element => !relation.contains(element) &&
              overlaps(relationRect, element.getBoundingClientRect(), -4))
            .map(element => (element.textContent || '').trim().slice(0, 40));
          if (coveredText.length) {
            problems.push({
              reason: 'architecture-relation-label-covers-text', view: viewId,
              relation: relation.dataset.relationId, text: coveredText.slice(0, 3),
            });
          }
        });
        const architectureRelations = [...view.querySelectorAll('.mv-architecture-relation[data-relation-id]')];
        architectureRelations.forEach((relation, index) => {
          architectureRelations.slice(index + 1).forEach(other => {
            if (overlaps(relation.getBoundingClientRect(), other.getBoundingClientRect(), 2)) {
              problems.push({
                reason: 'architecture-relation-label-collision', view: viewId,
                relation: relation.dataset.relationId, other: other.dataset.relationId,
              });
            }
          });
        });
        const architecturePaths = [...view.querySelectorAll('.mv-architecture-wire-path[data-wire-relation-id]')];
        if (architecturePaths.length !== architectureRelations.length) {
          problems.push({
            reason: 'architecture-wire-count', view: viewId,
            relations: architectureRelations.length, paths: architecturePaths.length,
          });
        }
        const borderDistance = (point, rect) => {
          const dx = point.x < rect.left ? rect.left - point.x : point.x > rect.right ? point.x - rect.right : 0;
          const dy = point.y < rect.top ? rect.top - point.y : point.y > rect.bottom ? point.y - rect.bottom : 0;
          if (dx && dy) return Math.hypot(dx, dy);
          if (dx) return dx;
          if (dy) return dy;
          return Math.min(
            Math.abs(point.x - rect.left), Math.abs(point.x - rect.right),
            Math.abs(point.y - rect.top), Math.abs(point.y - rect.bottom),
          );
        };
        architecturePaths.forEach(path => {
          const relationId = path.dataset.wireRelationId || '';
          const relation = view.querySelector(`.mv-architecture-relation[data-relation-id="${CSS.escape(relationId)}"]`);
          const subject = view.querySelector(`[data-entity-id="${CSS.escape(path.dataset.subject || '')}"]`);
          const object = view.querySelector(`[data-entity-id="${CSS.escape(path.dataset.object || '')}"]`);
          const d = path.getAttribute('d') || '';
          const numbers = d.match(/-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?/gi) || [];
          const style = getComputedStyle(path);
          const routeScope = path.dataset.routeScope || 'standard';
          if (routeScope === 'support-map') {
            const relationRect = relation?.getBoundingClientRect();
            const subjectRect = subject?.getBoundingClientRect();
            const targetText = object?.querySelector('h3')?.textContent?.trim() || '';
            const targetCarrier = relation?.querySelector('.mv-support-map-target');
            const sourceRegion = subject?.closest('.mv-region[data-role="support"]');
            const labelInsideSource = Boolean(relationRect && subjectRect &&
              relationRect.left >= subjectRect.left - 2 &&
              relationRect.right <= subjectRect.right + 2 &&
              relationRect.top >= subjectRect.top - 2 &&
              relationRect.bottom <= subjectRect.bottom + 2);
            const validSupportMap = Boolean(
              relation && subject && object && sourceRegion && !sourceRegion.contains(object) &&
              ['provides', 'dependsOn', 'enables'].includes(relation.dataset.kind || '') &&
              relation.dataset.routeFamily === 'support' &&
              path.dataset.routeFamily === 'support' && !d.trim() && style.display === 'none' &&
              targetCarrier && targetText && targetCarrier.textContent.trim() === targetText &&
              labelInsideSource
            );
            if (!validSupportMap) {
              problems.push({
                reason: 'architecture-support-map-invalid', view: viewId,
                relation: relationId, targetText,
                targetCarrier: targetCarrier?.textContent?.trim() || '',
                labelInsideSource, pathDisplay: style.display, pathData: d,
              });
            }
            return;
          }
          let length = 0;
          try { length = path.getTotalLength(); } catch (_) { length = 0; }
          if (!relation || !subject || !object || !d.trim() || numbers.length < 4 ||
              !numbers.every(number => Number.isFinite(Number(number))) ||
              !Number.isFinite(length) || length <= 4 || parseFloat(style.strokeWidth || 0) <= 0 ||
              !style.stroke || style.stroke === 'none') {
            problems.push({ reason: 'architecture-wire-invalid', view: viewId, relation: relationId });
            return;
          }
          if (Number(path.dataset.routeHits || 0) !== 0) {
            problems.push({
              reason: 'architecture-wire-route-blocked', view: viewId,
              relation: relationId, hits: path.dataset.routeHits || '',
            });
          }
          const routeLength = Number(path.dataset.routeLength);
          const directDistance = Number(path.dataset.directDistance);
          const detourRatio = Number(path.dataset.detourRatio);
          const turnCount = Number(path.dataset.turnCount);
          if (!Number.isFinite(routeLength) || routeLength <= 0 ||
              !Number.isFinite(directDistance) || directDistance <= 0 ||
              !Number.isFinite(detourRatio) || detourRatio < 1 ||
              !Number.isInteger(turnCount) || turnCount < 0) {
            problems.push({
              reason: 'architecture-wire-route-metrics-invalid', view: viewId,
              relation: relationId,
            });
          } else {
            const detourLimit = routeScope === 'local' ? 1.8 : 3.6;
            if (routeScope === 'fallback' || detourRatio > detourLimit) {
              problems.push({
                reason: 'architecture-wire-excessive-detour', view: viewId,
                relation: relationId, routeScope,
                routeLength: Number(routeLength.toFixed(2)),
                directDistance: Number(directDistance.toFixed(2)),
                detourRatio: Number(detourRatio.toFixed(3)),
                turnCount, limit: detourLimit,
              });
            }
          }
          const matrix = path.getScreenCTM();
          if (!matrix) {
            problems.push({ reason: 'architecture-wire-no-matrix', view: viewId, relation: relationId });
            return;
          }
          const startPoint = path.getPointAtLength(0);
          const endPoint = path.getPointAtLength(length);
          const start = new DOMPoint(startPoint.x, startPoint.y).matrixTransform(matrix);
          const end = new DOMPoint(endPoint.x, endPoint.y).matrixTransform(matrix);
          const subjectFootprint = semanticFootprint(subject);
          const objectFootprint = semanticFootprint(object);
          const subjectRect = subjectFootprint.getBoundingClientRect();
          const objectRect = objectFootprint.getBoundingClientRect();
          const routeFamily = path.dataset.routeFamily || relation.dataset.routeFamily || '';
          const subjectExternal = subject.dataset.boundary === 'external';
          const objectExternal = object.dataset.boundary === 'external';
          const hasExternalEndpoint = subjectExternal || objectExternal;
          const requiresBoundaryPort = requiresBoundaryPortRoute(subject, object, routeFamily);
          const boundaryPortRegionId = path.getAttribute('data-boundary-port-region') || '';
          const boundaryPortEndpoint = path.getAttribute('data-boundary-port-endpoint') || '';
          let startGap = borderDistance(start, subjectRect);
          let endGap = borderDistance(end, objectRect);
          if (requiresBoundaryPort && path.dataset.routeScope !== 'boundary-port') {
            problems.push({
              reason: 'architecture-wire-missing-boundary-port', view: viewId,
              relation: relationId, routeFamily,
              routeScope: path.dataset.routeScope || 'standard',
            });
          }
          if (!requiresBoundaryPort && path.dataset.routeScope === 'boundary-port') {
            problems.push({
              reason: 'architecture-wire-unexpected-boundary-port', view: viewId,
              relation: relationId, routeFamily,
            });
          }
          if (path.dataset.routeScope === 'boundary-port' || boundaryPortRegionId || boundaryPortEndpoint) {
            const boundary = boundaryPortRegionId ? view.querySelector(
              `[data-region-id="${CSS.escape(boundaryPortRegionId)}"]`,
            ) : null;
            const internalEntity = boundaryPortEndpoint === 'subject' ? subject : object;
            const externalRect = boundaryPortEndpoint === 'subject' ? objectRect : subjectRect;
            const portPoint = boundaryPortEndpoint === 'subject' ? start : end;
            const boundaryRect = boundary?.getBoundingClientRect();
            const portGap = boundaryRect ? borderDistance(portPoint, boundaryRect) : Infinity;
            const horizontalBorder = boundaryRect && (
              Math.abs(portPoint.y - boundaryRect.top) <= 3 ||
              Math.abs(portPoint.y - boundaryRect.bottom) <= 3
            );
            const verticalBorder = boundaryRect && (
              Math.abs(portPoint.x - boundaryRect.left) <= 3 ||
              Math.abs(portPoint.x - boundaryRect.right) <= 3
            );
            const projectionAligned = horizontalBorder ?
              portPoint.x >= externalRect.left - 8 && portPoint.x <= externalRect.right + 8 :
              verticalBorder ? portPoint.y >= externalRect.top - 8 && portPoint.y <= externalRect.bottom + 8 : false;
            const boundaryPortOffsetRatio = Number(
              path.getAttribute('data-boundary-port-offset-ratio'),
            );
            const boundedPortOffset = Number.isFinite(boundaryPortOffsetRatio) &&
              boundaryPortOffsetRatio >= 0 && boundaryPortOffsetRatio <= .35;
            const validBoundaryPort = path.dataset.routeScope === 'boundary-port' &&
              Boolean(boundary) && ['entry', 'output'].includes(routeFamily) &&
              ['subject', 'object'].includes(boundaryPortEndpoint) &&
              boundary.contains(internalEntity) && portGap <= 3 &&
              (projectionAligned || boundedPortOffset);
            let boundaryInteriorSamples = 0;
            if (boundaryRect && length > 0) {
              const sampleCount = Math.max(24, Math.ceil(length / 2));
              for (let sampleIndex = 1; sampleIndex < sampleCount; sampleIndex += 1) {
                const sample = path.getPointAtLength(length * sampleIndex / sampleCount);
                const point = new DOMPoint(sample.x, sample.y).matrixTransform(matrix);
                if (point.x > boundaryRect.left + 1 && point.x < boundaryRect.right - 1 &&
                    point.y > boundaryRect.top + 1 && point.y < boundaryRect.bottom - 1) {
                  boundaryInteriorSamples += 1;
                }
              }
            }
            if (!validBoundaryPort) {
              problems.push({
                reason: 'architecture-wire-boundary-port-invalid', view: viewId,
                relation: relationId, routeFamily, boundaryPortRegionId,
                boundaryPortEndpoint, portGap: Number.isFinite(portGap) ? Number(portGap.toFixed(2)) : null,
                projectionAligned, boundaryPortOffsetRatio,
              });
            } else if (boundaryInteriorSamples > 0) {
              problems.push({
                reason: 'architecture-wire-boundary-port-enters-system', view: viewId,
                relation: relationId, boundaryPortRegionId, boundaryInteriorSamples,
              });
            } else if (boundaryPortEndpoint === 'subject') {
              startGap = portGap;
            } else {
              endGap = portGap;
            }
          }
          if (!Number.isFinite(startGap) || !Number.isFinite(endGap) || startGap > 3 || endGap > 3) {
            problems.push({
              reason: 'architecture-wire-endpoint-gap', view: viewId, relation: relationId,
              startGap: Number(startGap.toFixed(2)), endGap: Number(endGap.toFixed(2)),
            });
          }
          const endpointFacingComponent = (side, point, otherRect) => {
            const nearest = {
              x: Math.max(otherRect.left, Math.min(otherRect.right, point.x)),
              y: Math.max(otherRect.top, Math.min(otherRect.bottom, point.y)),
            };
            const dx = nearest.x - point.x;
            const dy = nearest.y - point.y;
            if (side === 'left') return -dx;
            if (side === 'right') return dx;
            if (side === 'top') return -dy;
            if (side === 'bottom') return dy;
            return 0;
          };
          const facingFamilies = new Set(['entry', 'main', 'internal', 'dependency', 'output', 'port']);
          const fromComponent = endpointFacingComponent(
            path.dataset.fromSide || '', start, objectRect,
          );
          const toComponent = endpointFacingComponent(
            path.dataset.toSide || '', end, subjectRect,
          );
          if (path.dataset.routeScope !== 'boundary-port' && facingFamilies.has(routeFamily) &&
              (fromComponent < -8 || toComponent < -8)) {
            problems.push({
              reason: 'architecture-wire-facing-away', view: viewId,
              relation: relationId, routeFamily,
              fromSide: path.dataset.fromSide || '',
              toSide: path.dataset.toSide || '',
              fromComponent: Number(fromComponent.toFixed(2)),
              toComponent: Number(toComponent.toFixed(2)),
            });
          }
          const gapX = Math.max(subjectRect.left - objectRect.right,
            objectRect.left - subjectRect.right, 0);
          const gapY = Math.max(subjectRect.top - objectRect.bottom,
            objectRect.top - subjectRect.bottom, 0);
          const endpointSeparation = Math.hypot(gapX, gapY);
          const visualDetourRatio = length / Math.max(24, endpointSeparation);
          const visualDetourFamilies = new Set(['main', 'internal', 'dependency', 'output']);
          if (!hasExternalEndpoint && visualDetourFamilies.has(routeFamily) &&
              visualDetourRatio > 4.5) {
            problems.push({
              reason: 'architecture-wire-visual-detour', view: viewId,
              relation: relationId, routeFamily,
              routeLength: Number(length.toFixed(2)),
              endpointSeparation: Number(endpointSeparation.toFixed(2)),
              visualDetourRatio: Number(visualDetourRatio.toFixed(3)),
              limit: 4.5,
            });
          }
          const subjectMain = subject.closest('.mv-region--container[data-role="main"]');
          const objectMain = object.closest('.mv-region--container[data-role="main"]');
          const commonMain = subjectMain && subjectMain === objectMain ? subjectMain : null;
          const directRegionChild = (container, node) => {
            let region = node?.closest('.mv-region') || null;
            while (region && region.parentElement !== container) {
              const parent = region.parentElement?.closest('.mv-region') || null;
              if (!parent || parent === region) return null;
              region = parent;
            }
            return region?.parentElement === container ? region : null;
          };
          const subjectDirectRegion = commonMain ? directRegionChild(commonMain, subject) : null;
          const objectDirectRegion = commonMain ? directRegionChild(commonMain, object) : null;
          const directRegions = commonMain ? [...commonMain.children].filter(child =>
            child.classList?.contains('mv-region')) : [];
          const subjectRegionIndex = directRegions.indexOf(subjectDirectRegion);
          const objectRegionIndex = directRegions.indexOf(objectDirectRegion);
          const longCrossBand = Boolean(commonMain && subjectDirectRegion && objectDirectRegion &&
            subjectDirectRegion !== objectDirectRegion &&
            subjectDirectRegion.classList.contains('mv-region--band') &&
            objectDirectRegion.classList.contains('mv-region--band') &&
            Math.abs(subjectRegionIndex - objectRegionIndex) >= 2 &&
            gapY >= 140);
          const laneMarker = view.querySelector(
            `[data-connector-lane-for="${CSS.escape(relationId)}"]`,
          );
          if (path.dataset.routeScope === 'lane') {
            const markerRect = laneMarker?.getBoundingClientRect();
            const laneRegionId = path.getAttribute('data-lane-region') || '';
            const laneSide = path.getAttribute('data-lane-side') || '';
            const commonMainRect = commonMain?.getBoundingClientRect();
            const directRegionRects = directRegions.map(region => region.getBoundingClientRect());
            const rootClearance = markerRect && commonMainRect ?
              (laneSide === 'left' ? markerRect.left - commonMainRect.left :
                laneSide === 'right' ? commonMainRect.right - markerRect.right : -Infinity) : -Infinity;
            const bandClearance = markerRect && directRegionRects.length ?
              (laneSide === 'left' ? Math.min(...directRegionRects.map(rect => rect.left - markerRect.right)) :
                laneSide === 'right' ? Math.min(...directRegionRects.map(rect => markerRect.left - rect.right)) : -Infinity) : -Infinity;
            const gutterClearance = Math.min(rootClearance, bandClearance);
            let samplesInsideMarker = 0;
            if (markerRect && length > 0) {
              const markerSampleCount = Math.max(40, Math.ceil(length / 3));
              for (let step = 0; step <= markerSampleCount; step += 1) {
                const sample = path.getPointAtLength(length * step / markerSampleCount);
                const point = new DOMPoint(sample.x, sample.y).matrixTransform(matrix);
                if (point.x >= markerRect.left - 2 && point.x <= markerRect.right + 2 &&
                    point.y >= markerRect.top - 2 && point.y <= markerRect.bottom + 2) {
                  samplesInsideMarker += 1;
                }
              }
            }
            const validLane = longCrossBand && Boolean(laneMarker) && visible(laneMarker) &&
              Math.min(markerRect?.width || 0, markerRect?.height || 0) >= 14 &&
              Boolean(commonMain?.contains(laneMarker)) &&
              laneRegionId === (commonMain?.dataset.regionId || '') &&
              ['left', 'right'].includes(laneSide) && samplesInsideMarker >= 2 &&
              gutterClearance >= 10;
            if (!validLane) {
              problems.push({
                reason: 'architecture-wire-lane-invalid', view: viewId,
                relation: relationId, laneRegionId, laneSide, samplesInsideMarker,
                gutterClearance: Number.isFinite(gutterClearance) ?
                  Number(gutterClearance.toFixed(2)) : null,
              });
            }
          }
          if (longCrossBand && path.dataset.routeScope !== 'lane') {
            const borderRects = [commonMain, ...directRegions].filter(Boolean).map(region => ({
              id: region.dataset.regionId || '', rect: region.getBoundingClientRect(),
            }));
            const hugSampleCount = Math.max(80, Math.ceil(length / 2));
            let longestHug = 0;
            let currentHug = 0;
            let previousPoint = null;
            let previousSignature = '';
            for (let step = 0; step <= hugSampleCount; step += 1) {
              const sample = path.getPointAtLength(length * step / hugSampleCount);
              const point = new DOMPoint(sample.x, sample.y).matrixTransform(matrix);
              let signature = '';
              let nearestDistance = Infinity;
              borderRects.forEach(({ id, rect }) => {
                const candidates = [
                  { side: 'left', distance: Math.abs(point.x - rect.left), projected: point.y >= rect.top && point.y <= rect.bottom },
                  { side: 'right', distance: Math.abs(point.x - rect.right), projected: point.y >= rect.top && point.y <= rect.bottom },
                  { side: 'top', distance: Math.abs(point.y - rect.top), projected: point.x >= rect.left && point.x <= rect.right },
                  { side: 'bottom', distance: Math.abs(point.y - rect.bottom), projected: point.x >= rect.left && point.x <= rect.right },
                ];
                candidates.forEach(candidate => {
                  if (candidate.projected && candidate.distance < 8 && candidate.distance < nearestDistance) {
                    nearestDistance = candidate.distance;
                    signature = `${id}:${candidate.side}`;
                  }
                });
              });
              const increment = previousPoint ? Math.hypot(point.x - previousPoint.x, point.y - previousPoint.y) : 0;
              currentHug = signature && signature === previousSignature ? currentHug + increment : 0;
              longestHug = Math.max(longestHug, currentHug);
              previousPoint = point;
              previousSignature = signature;
            }
            if (longestHug >= 48) {
              problems.push({
                reason: 'architecture-wire-hugs-region-border', view: viewId,
                relation: relationId, longestHug: Number(longestHug.toFixed(2)),
              });
            }
          }
          if (!crossBoundaryRouteFamilies.has(routeFamily) && !hasExternalEndpoint) {
            const commonRegion = closestCommonSemanticContainer(subject, object);
            if (commonRegion) {
              const commonRect = commonRegion.getBoundingClientRect();
              const escapeSampleCount = Math.max(80, Math.ceil(length / 2));
              let maxEscape = 0;
              for (let step = 0; step <= escapeSampleCount; step += 1) {
                const sample = path.getPointAtLength(length * step / escapeSampleCount);
                const point = new DOMPoint(sample.x, sample.y).matrixTransform(matrix);
                const horizontalEscape = Math.max(
                  commonRect.left - point.x,
                  point.x - commonRect.right,
                  0,
                );
                const verticalEscape = Math.max(
                  commonRect.top - point.y,
                  point.y - commonRect.bottom,
                  0,
                );
                maxEscape = Math.max(maxEscape, horizontalEscape, verticalEscape);
              }
              if (maxEscape > 8) {
                problems.push({
                  reason: 'architecture-wire-escapes-common-region',
                  view: viewId,
                  relation: relationId,
                  commonRegion: commonRegion.dataset.regionId || '',
                  routeFamily,
                  maxEscape: Number(maxEscape.toFixed(2)),
                });
              }
            }
          }
          const otherEntities = [...view.querySelectorAll('.mv-entity[data-entity-id]')]
            .filter(entity => entity !== subject && entity !== object);
          let crossesEntity = false;
          const sampleCount = Math.max(40, Math.ceil(length / 2));
          for (let step = 1; step < sampleCount && !crossesEntity; step += 1) {
            const sample = path.getPointAtLength(length * step / sampleCount);
            const point = new DOMPoint(sample.x, sample.y).matrixTransform(matrix);
            crossesEntity = otherEntities.some(entity => {
              const rect = entity.getBoundingClientRect();
              return point.x > rect.left + 2 && point.x < rect.right - 2 &&
                point.y > rect.top + 2 && point.y < rect.bottom - 2;
            });
          }
          if (crossesEntity) {
            problems.push({ reason: 'architecture-wire-crosses-entity', view: viewId, relation: relationId });
          }
          const nonEndpointText = architectureText.filter(element =>
            !subjectFootprint.contains(element) && !objectFootprint.contains(element),
          );
          let crossedText = '';
          for (let step = 1; step < sampleCount && !crossedText; step += 1) {
            const sample = path.getPointAtLength(length * step / sampleCount);
            const point = new DOMPoint(sample.x, sample.y).matrixTransform(matrix);
            const hit = nonEndpointText.find(element => {
              const rect = element.getBoundingClientRect();
              return point.x > rect.left - 1 && point.x < rect.right + 1 &&
                point.y > rect.top - 1 && point.y < rect.bottom + 1;
            });
            if (hit) crossedText = (hit.textContent || '').trim().slice(0, 40);
          }
          if (crossedText) {
            problems.push({
              reason: 'architecture-wire-crosses-text', view: viewId,
              relation: relationId, text: crossedText,
            });
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
          const targetElements = targets.map(target =>
            view.querySelector(`[data-region-id="${CSS.escape(target)}"]`),
          ).filter(Boolean);
          if (targetElements.length && visible(region)) {
            const rail = region.getBoundingClientRect();
            const boxes = targetElements.map(target => target.getBoundingClientRect());
            const targetTop = Math.min(...boxes.map(box => box.top));
            const targetBottom = Math.max(...boxes.map(box => box.bottom));
            const targetLeft = Math.min(...boxes.map(box => box.left));
            const targetRight = Math.max(...boxes.map(box => box.right));
            const spansTargets = rail.top <= targetTop + 7 && rail.bottom >= targetBottom - 7 &&
              rail.height >= (targetBottom - targetTop) * .82;
            const sitsBesideTargets = rail.left >= targetRight - 4 || rail.right <= targetLeft + 4;
            const spansTargetWidth = rail.left <= targetLeft + 7 && rail.right >= targetRight - 7 &&
              rail.width >= (targetRight - targetLeft) * .82;
            const sitsAboveOrBelowTargets = rail.top >= targetBottom - 4 || rail.bottom <= targetTop + 4;
            const spatial = (spansTargets && sitsBesideTargets) ||
              (spansTargetWidth && sitsAboveOrBelowTargets);
            if (region.dataset.layoutState !== 'drawn' || !spatial) {
              problems.push({
                reason: 'crosscut-not-spatial', view: viewId, region: region.dataset.regionId,
                state: region.dataset.layoutState || '', spansTargets, sitsBesideTargets,
                spansTargetWidth, sitsAboveOrBelowTargets,
              });
            }
          }
        });
        let equivalentContainerDepth = 0;
        [...view.querySelectorAll('.mv-region--container')]
          .filter(container => visible(container) && hasSemanticOwner(container)).forEach(container => {
          let depth = 1;
          let current = container;
          while (current) {
            if (current.dataset.role === 'inset' || current.dataset.role === 'support') break;
            const parent = closestSemanticContainer(current.parentElement);
            if (!parent) break;
            if (parent.dataset.role === 'inset' || parent.dataset.role === 'support') break;
            const currentRect = current.getBoundingClientRect();
            const parentRect = parent.getBoundingClientRect();
            if (!parentRect.width || currentRect.width / parentRect.width < .84) break;
            depth += 1;
            current = parent;
          }
          equivalentContainerDepth = Math.max(equivalentContainerDepth, depth);
        });
        if (view.querySelector('.mv-diagram')?.getBoundingClientRect().width >= 650 &&
            equivalentContainerDepth >= 3) {
          problems.push({ reason: 'architecture-card-wall', view: viewId, depth: equivalentContainerDepth });
        }
      }

      if (kind === 'flow') {
        const connectors = [...view.querySelectorAll('.mv-connector[data-relation-id]')];
        if (!connectors.length) problems.push({ reason: 'flow-without-connector', view: viewId });
        const sequence = view.querySelector('.mv-flow-sequence');
        if (sequence && visible(sequence)) {
          const sequenceRect = sequence.getBoundingClientRect();
          if (sequence.scrollWidth > sequence.clientWidth + 1) {
            problems.push({
              reason: 'flow-main-path-overflow', view: viewId,
              clientWidth: sequence.clientWidth,
              scrollWidth: sequence.scrollWidth,
            });
          }
          const sequenceItems = [...sequence.children].filter(visible);
          if (sequenceItems.length) {
            const itemRects = sequenceItems.map(item => item.getBoundingClientRect());
            const diagramRect = diagram.getBoundingClientRect();
            itemRects.forEach((rect, index) => {
              const outsideSequence = rect.left < sequenceRect.left - 1 ||
                rect.right > sequenceRect.right + 1 ||
                rect.top < sequenceRect.top - 1 || rect.bottom > sequenceRect.bottom + 1;
              const outsideDiagram = rect.left < diagramRect.left - 1 ||
                rect.right > diagramRect.right + 1 ||
                rect.top < diagramRect.top - 1 || rect.bottom > diagramRect.bottom + 1;
              if (outsideSequence || outsideDiagram) {
                problems.push({
                  reason: 'flow-main-path-clipped', view: viewId, index,
                  outsideSequence, outsideDiagram,
                });
              }
            });
            const contentTop = Math.min(...itemRects.map(rect => rect.top));
            const contentBottom = Math.max(...itemRects.map(rect => rect.bottom));
            const contentHeight = Math.max(1, contentBottom - contentTop);
            if (sequenceRect.height > Math.max(contentHeight + 80, contentHeight * 1.8)) {
              problems.push({
                reason: 'flow-sequence-excessive-whitespace', view: viewId,
                sequenceHeight: Number(sequenceRect.height.toFixed(1)),
                contentHeight: Number(contentHeight.toFixed(1)),
              });
            }
          }
        }
        const declaredRelationIds = (view.dataset.declaredRelationIds || '')
          .trim().split(/\s+/).filter(Boolean);
        const connectorRelationIds = connectors
          .map(connector => connector.dataset.relationId).filter(Boolean);
        const missingDirected = declaredRelationIds.filter(
          relationId => !connectorRelationIds.includes(relationId),
        );
        const extraDirected = connectorRelationIds.filter(
          relationId => !declaredRelationIds.includes(relationId),
        );
        const duplicateDirected = [...new Set(connectorRelationIds.filter(
          (relationId, index) => connectorRelationIds.indexOf(relationId) !== index,
        ))];
        if (missingDirected.length || extraDirected.length || duplicateDirected.length) {
          problems.push({
            reason: 'flow-directed-relation-mismatch', view: viewId,
            missing: missingDirected, extra: extraDirected, duplicates: duplicateDirected,
          });
        }
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
        const mainPathRelationIds = new Set(
          sequence ? [...sequence.querySelectorAll('.mv-connector[data-relation-id]')]
            .map(connector => connector.dataset.relationId).filter(Boolean) : [],
        );
        const junctionRelationIds = new Set();
        const junctionDescriptors = [];
        [...view.querySelectorAll('.mv-flow-junction')].forEach((junction, junctionIndex) => {
          const junctionKind = junction.dataset.junctionKind || '';
          const buses = [...junction.children]
            .filter(child => child.classList.contains('mv-flow-junction-bus'));
          const lanesRoot = [...junction.children]
            .find(child => child.classList.contains('mv-flow-junction-lanes'));
          const lanes = lanesRoot ? [...lanesRoot.children]
            .filter(child => child.classList.contains('mv-flow-junction-lane')) : [];
          const junctionConnectors = [...junction.querySelectorAll(
            '.mv-connector--junction[data-relation-id]',
          )];
          const actualIds = junctionConnectors
            .map(connector => connector.dataset.relationId).filter(Boolean);
          const declaredIds = (junction.dataset.junctionRelationIds || '')
            .trim().split(/\s+/).filter(Boolean);
          const duplicates = actualIds.filter(
            (relationId, index) => actualIds.indexOf(relationId) !== index,
          );
          const declaredDuplicates = declaredIds.filter(
            (relationId, index) => declaredIds.indexOf(relationId) !== index,
          );
          const missing = declaredIds.filter(relationId => !actualIds.includes(relationId));
          const extra = actualIds.filter(relationId => !declaredIds.includes(relationId));
          const repeated = actualIds.filter(relationId => junctionRelationIds.has(relationId));
          if (missing.length || extra.length || duplicates.length || declaredDuplicates.length ||
              repeated.length || declaredIds.length !== actualIds.length ||
              Number(junction.dataset.junctionRelationCount || -1) !== actualIds.length) {
            problems.push({
              reason: 'flow-junction-relation-mismatch', view: viewId,
              junction: junctionIndex, missing, extra,
              duplicates: [...new Set([...duplicates, ...declaredDuplicates])],
              repeated: [...new Set(repeated)],
            });
          }
          actualIds.forEach(relationId => junctionRelationIds.add(relationId));

          const subjects = new Set(junctionConnectors
            .map(connector => connector.dataset.subject).filter(Boolean));
          const objects = new Set(junctionConnectors
            .map(connector => connector.dataset.object).filter(Boolean));
          const junctionRect = junction.getBoundingClientRect();
          if (junctionKind === 'splitmerge') {
            const sourceId = junction.dataset.junctionSourceId || '';
            const targetId = junction.dataset.junctionTargetId || '';
            const branchIds = lanes.map(lane => lane.dataset.junctionBranchId || '');
            const branchSet = new Set(branchIds.filter(Boolean));
            let topologyValid = lanes.length >= 2 && buses.length === 2 &&
              branchIds.length === branchSet.size && !branchIds.includes('') &&
              Number(junction.dataset.junctionBranchCount || -1) === branchSet.size &&
              junctionConnectors.length >= branchSet.size * 2;
            const laneTopology = [];
            lanes.forEach(lane => {
              const branchId = lane.dataset.junctionBranchId || '';
              const children = [...lane.children];
              const outboundRoot = children[0];
              const branchStep = children[1];
              const inboundRoot = children[2];
              const outbound = outboundRoot && outboundRoot.classList.contains('mv-flow-junction-relations')
                ? [...outboundRoot.querySelectorAll(':scope > .mv-connector--junction[data-relation-id]')] : [];
              const inbound = inboundRoot && inboundRoot.classList.contains('mv-flow-junction-relations')
                ? [...inboundRoot.querySelectorAll(':scope > .mv-connector--junction[data-relation-id]')] : [];
              const branchEntity = branchStep && branchStep.classList.contains('mv-flow-step')
                ? branchStep.querySelector(':scope > .mv-entity[data-entity-id]') : null;
              const laneValid = children.length === 3 && outbound.length >= 1 && inbound.length >= 1 &&
                branchEntity && branchEntity.dataset.entityId === branchId &&
                outbound.every(connector => connector.dataset.subject === sourceId &&
                  connector.dataset.object === branchId) &&
                inbound.every(connector => connector.dataset.subject === branchId &&
                  connector.dataset.object === targetId);
              topologyValid = topologyValid && laneValid;
              laneTopology.push({ branchId, outbound, inbound });
            });
            const outboundObjects = new Set(laneTopology.flatMap(lane =>
              lane.outbound.map(connector => connector.dataset.object).filter(Boolean)));
            const inboundSubjects = new Set(laneTopology.flatMap(lane =>
              lane.inbound.map(connector => connector.dataset.subject).filter(Boolean)));
            topologyValid = topologyValid &&
              outboundObjects.size === branchSet.size && inboundSubjects.size === branchSet.size &&
              [...branchSet].every(branchId => outboundObjects.has(branchId) && inboundSubjects.has(branchId));
            if (!topologyValid) {
              problems.push({
                reason: 'flow-splitmerge-topology', view: viewId,
                junction: junctionIndex, branches: branchIds,
                source: sourceId, target: targetId,
              });
            }

            const anchors = [...junction.children]
              .filter(child => child.classList.contains('mv-flow-junction-anchor'));
            const busRects = buses.map(bus => bus.getBoundingClientRect());
            const lanesRect = lanesRoot ? lanesRoot.getBoundingClientRect() : null;
            const orderedParts = anchors.length === 2 && lanesRoot
              ? [anchors[0], buses[0], lanesRoot, buses[1], anchors[1]] : [];
            const orderedRects = orderedParts.map(part => part.getBoundingClientRect());
            let continuityValid = topologyValid && orderedRects.length === 5 &&
              orderedRects.every(rect => rect.width > 1 && rect.height > 1) &&
              orderedRects.every((rect, index) => index === orderedRects.length - 1 ||
                rect.right <= orderedRects[index + 1].left + 1) &&
              orderedRects.every(rect => rect.left >= junctionRect.left - 1 &&
                rect.right <= junctionRect.right + 1 && rect.top >= junctionRect.top - 1 &&
                rect.bottom <= junctionRect.bottom + 1) &&
              junction.scrollWidth <= junction.clientWidth + 1;
            const busLineRanges = buses.map((bus, index) => {
              const rect = busRects[index];
              const line = getComputedStyle(bus, '::before');
              const top = Number.parseFloat(line.top);
              const bottom = Number.parseFloat(line.bottom);
              const width = Number.parseFloat(line.width);
              const valid = visible(bus) && line.content !== 'none' && line.display !== 'none' &&
                line.visibility !== 'hidden' && Number(line.opacity || 1) > .05 &&
                Number.isFinite(top) && Number.isFinite(bottom) &&
                Number.isFinite(width) && width >= 2 && rect.height - top - bottom > 1;
              return { valid, start: rect.top + top, end: rect.bottom - bottom };
            });
            continuityValid = continuityValid && busLineRanges.length === 2 &&
              busLineRanges.every(range => range.valid);
            if (continuityValid && lanes.length) {
              const firstLaneRect = lanes[0].getBoundingClientRect();
              const lastLaneRect = lanes[lanes.length - 1].getBoundingClientRect();
              continuityValid = busLineRanges.every(range =>
                range.start >= firstLaneRect.top - 1 && range.start <= firstLaneRect.bottom + 1 &&
                range.end >= lastLaneRect.top - 1 && range.end <= lastLaneRect.bottom + 1);
            }
            const sourceTrunk = anchors[0] ? getComputedStyle(anchors[0], '::after') : null;
            const targetTrunk = anchors[1] ? getComputedStyle(anchors[1], '::before') : null;
            continuityValid = continuityValid && sourceTrunk && targetTrunk &&
              sourceTrunk.content !== 'none' && targetTrunk.content !== 'none' &&
              Number.parseFloat(sourceTrunk.width) > 1 && Number.parseFloat(targetTrunk.width) > 1;
            laneTopology.forEach(lane => {
              lane.outbound.forEach(connector => {
                const carrier = connector.querySelector(':scope > span');
                if (!carrier || !visible(connector)) {
                  continuityValid = false;
                  return;
                }
                const carrierRect = carrier.getBoundingClientRect();
                const line = getComputedStyle(carrier, '::before');
                const arrow = getComputedStyle(carrier, '::after');
                const left = Number.parseFloat(line.left);
                const busCenter = busRects[0].left + busRects[0].width / 2;
                if (!Number.isFinite(left) || Math.abs(carrierRect.left + left - busCenter) > 2.5 ||
                    arrow.content === 'none' || arrow.display === 'none' ||
                    Number.parseFloat(arrow.borderRightWidth) < 1.5 ||
                    !visible(connector.querySelector(':scope > small'))) continuityValid = false;
              });
              lane.inbound.forEach(connector => {
                const carrier = connector.querySelector(':scope > span');
                if (!carrier || !visible(connector)) {
                  continuityValid = false;
                  return;
                }
                const carrierRect = carrier.getBoundingClientRect();
                const line = getComputedStyle(carrier, '::before');
                const arrow = getComputedStyle(carrier, '::after');
                const right = Number.parseFloat(line.right);
                const busCenter = busRects[1].left + busRects[1].width / 2;
                if (!Number.isFinite(right) || Math.abs(carrierRect.right - right - busCenter) > 2.5 ||
                    arrow.content === 'none' || arrow.display === 'none' ||
                    Number.parseFloat(arrow.borderRightWidth) < 1.5 ||
                    !visible(connector.querySelector(':scope > small'))) continuityValid = false;
              });
            });
            if (!continuityValid) {
              problems.push({
                reason: 'flow-splitmerge-continuity', view: viewId,
                junction: junctionIndex, buses: buses.length, lanes: lanes.length,
                width: Math.round(junctionRect.width), height: Math.round(junctionRect.height),
              });
            }
            junctionDescriptors.push({
              kind: junctionKind, sourceId, targetId, branches: [...branchSet].sort(),
            });
            return;
          }

          const bus = buses[0];
          const busRect = bus ? bus.getBoundingClientRect() : null;
          let shapeValid = ['fanout', 'fanin'].includes(junctionKind) &&
            buses.length === 1 && visible(bus) && lanes.length >= 2 &&
            junctionConnectors.length >= 2 &&
            junctionRect.width > 1 && junctionRect.height > 1;
          if (junctionKind === 'fanout') {
            shapeValid = shapeValid && subjects.size === 1 && objects.size >= 2 &&
              subjects.has(junction.dataset.junctionSourceId || '') &&
              Number(junction.dataset.junctionTargetCount || -1) === objects.size;
            junctionDescriptors.push({
              kind: junctionKind, sourceId: junction.dataset.junctionSourceId || '',
              targetId: '', branches: [...objects].sort(),
            });
          } else if (junctionKind === 'fanin') {
            shapeValid = shapeValid && subjects.size >= 2 && objects.size === 1 &&
              objects.has(junction.dataset.junctionTargetId || '') &&
              Number(junction.dataset.junctionSourceCount || -1) === subjects.size;
            junctionDescriptors.push({
              kind: junctionKind, sourceId: '',
              targetId: junction.dataset.junctionTargetId || '', branches: [...subjects].sort(),
            });
          }
          if (busRect && shapeValid) {
            const busCenter = busRect.left + busRect.width / 2;
            junctionConnectors.forEach(connector => {
              const carrier = connector.querySelector(':scope > span');
              if (!carrier) {
                shapeValid = false;
                return;
              }
              const carrierRect = carrier.getBoundingClientRect();
              const lineStyle = getComputedStyle(carrier, '::before');
              const left = Number.parseFloat(lineStyle.left);
              const right = Number.parseFloat(lineStyle.right);
              if (!Number.isFinite(left) || !Number.isFinite(right)) {
                shapeValid = false;
                return;
              }
              const lineStart = carrierRect.left + left;
              const lineEnd = carrierRect.right - right;
              const junctionGap = junctionKind === 'fanout'
                ? Math.abs(lineStart - busCenter)
                : Math.abs(lineEnd - busCenter);
              if (junctionGap > 2.5) shapeValid = false;
            });
          }
          if (!shapeValid) {
            problems.push({
              reason: 'flow-junction-shape', view: viewId,
              junction: junctionIndex, kind: junctionKind,
              buses: buses.length, lanes: lanes.length,
              subjects: subjects.size, objects: objects.size,
            });
          }
        });

        const descriptorKey = descriptor => descriptor.branches.join('\u0001');
        const splitmergeResiduals = [];
        junctionDescriptors.filter(descriptor => descriptor.kind === 'fanout').forEach(fanout => {
          junctionDescriptors.filter(descriptor => descriptor.kind === 'fanin').forEach(fanin => {
            if (fanout.branches.length >= 2 && descriptorKey(fanout) === descriptorKey(fanin)) {
              splitmergeResiduals.push({
                source: fanout.sourceId, target: fanin.targetId,
                branches: fanout.branches,
              });
            }
          });
        });
        if (splitmergeResiduals.length) {
          problems.push({
            reason: 'flow-splitmerge-residual', view: viewId,
            residuals: splitmergeResiduals,
          });
        }

        const residualConnectors = connectors.filter(connector =>
          !mainPathRelationIds.has(connector.dataset.relationId) &&
          !junctionRelationIds.has(connector.dataset.relationId),
        );
        const residualFanout = new Map();
        const residualFanin = new Map();
        residualConnectors.forEach(connector => {
          const subject = connector.dataset.subject || '';
          const object = connector.dataset.object || '';
          if (!residualFanout.has(subject)) residualFanout.set(subject, new Set());
          if (!residualFanin.has(object)) residualFanin.set(object, new Set());
          residualFanout.get(subject).add(object);
          residualFanin.get(object).add(subject);
        });
        const unconsolidatedFanout = [...residualFanout.entries()]
          .filter(([, targets]) => targets.size >= 2)
          .map(([subject, targets]) => ({ subject, targets: [...targets] }));
        const unconsolidatedFanin = [...residualFanin.entries()]
          .filter(([, sources]) => sources.size >= 2)
          .map(([object, sources]) => ({ object, sources: [...sources] }));
        if (unconsolidatedFanout.length || unconsolidatedFanin.length) {
          problems.push({
            reason: 'flow-unconsolidated-junction', view: viewId,
            fanout: unconsolidatedFanout, fanin: unconsolidatedFanin,
          });
        }
        const terminal = view.querySelector('[data-state-kind="terminal"],[data-state-kind="persistent"]');
        if (!terminal && view.dataset.readingKind !== 'cyclic') {
          problems.push({ reason: 'flow-without-terminal-or-cycle', view: viewId });
        }
      }

      if (kind === 'matrix') {
        const table = view.querySelector('table.mv-matrix');
        const orientation = table ? (table.dataset.orientation || 'options-as-columns') : '';
        if (!table || !['options-as-columns', 'facts-as-columns'].includes(orientation)) {
          problems.push({ reason: 'matrix-shape', view: viewId, orientation });
        } else if (orientation === 'facts-as-columns') {
          const facts = [...table.querySelectorAll('thead [data-fact-id]')];
          const rows = [...table.querySelectorAll('tbody tr')];
          const options = rows.map(row => row.querySelector('th[data-entity-id]')).filter(Boolean);
          if (options.length < 2 || facts.length < 1 || options.length !== rows.length) {
            problems.push({
              reason: 'matrix-shape', view: viewId, orientation,
              options: options.length, facts: facts.length, rows: rows.length,
            });
          }
          const factIds = facts.map(fact => fact.dataset.factId);
          rows.forEach(row => {
            const option = row.querySelector('th[data-entity-id]');
            const cells = [...row.querySelectorAll('td[data-target-id][data-matrix-cell-fact-id]')];
            const cellFactIds = cells.map(cell => cell.dataset.matrixCellFactId);
            const wrongTarget = cells.some(cell => !option || cell.dataset.targetId !== option.dataset.entityId);
            const missingFacts = factIds.filter(id => !cellFactIds.includes(id));
            const extraFacts = cellFactIds.filter(id => !factIds.includes(id));
            const duplicateFacts = [...new Set(cellFactIds.filter((id, index) => cellFactIds.indexOf(id) !== index))];
            if (cells.length !== facts.length || wrongTarget || missingFacts.length || extraFacts.length || duplicateFacts.length) {
              problems.push({
                reason: 'matrix-column-coverage', view: viewId,
                option: option ? option.dataset.entityId : '',
                cells: cells.length, facts: facts.length, wrongTarget,
                missingFacts, extraFacts, duplicateFacts,
              });
            }
          });
        } else {
          const options = [...table.querySelectorAll('thead [data-entity-id]')];
          if (options.length < 2) {
            problems.push({ reason: 'matrix-shape', view: viewId, orientation, options: options.length });
          }
          [...table.querySelectorAll('tbody tr[data-fact-id]')].forEach(row => {
            const cells = row.querySelectorAll('td[data-target-id][data-matrix-cell-fact-id]');
            if (cells.length !== options.length) {
              problems.push({ reason: 'matrix-row-coverage', view: viewId, fact: row.dataset.factId, cells: cells.length, options: options.length });
            }
          });
        }
        if (table) {
          const facts = orientation === 'facts-as-columns'
            ? [...table.querySelectorAll('thead [data-fact-id]')]
            : [...table.querySelectorAll('tbody tr[data-fact-id]')];
          const options = orientation === 'facts-as-columns'
            ? [...table.querySelectorAll('tbody th[data-entity-id]')]
            : [...table.querySelectorAll('thead th[data-entity-id]')];
          const factById = new Map(facts.map(fact => [fact.dataset.factId || '', fact]));
          const optionById = new Map(options.map(option => [option.dataset.entityId || '', option]));
          const factIds = [...factById.keys()].filter(Boolean);
          const optionIds = options.map(option => option.dataset.entityId || '').filter(Boolean);
          const expectedPairs = new Set(
            factIds.flatMap(factId => optionIds.map(optionId => `${factId}\u0000${optionId}`)),
          );
          const seenPairs = new Set();
          const cellIssues = [];
          const normalizeText = value => (value || '').replace(/\s+/g, ' ').trim();
          [...table.querySelectorAll('tbody td')].forEach((cell, index) => {
            const factId = cell.dataset.matrixCellFactId || '';
            const factRef = cell.dataset.factRef || '';
            const targetId = cell.dataset.targetId || '';
            const pair = `${factId}\u0000${targetId}`;
            const fact = factById.get(factId);
            const option = optionById.get(targetId);
            const row = cell.closest('tr');
            const rowFactId = row ? (row.dataset.factId || '') : '';
            const rowOption = row ? row.querySelector('th[data-entity-id]') : null;
            const rowOptionId = rowOption ? (rowOption.dataset.entityId || '') : '';
            const visibleText = normalizeText(cell.textContent || '');
            const declaredText = normalizeText(cell.dataset.matrixCellValue || '');
            const factSources = fact ? normalizeText(fact.getAttribute('data-source-blocks') || '') : '';
            const cellSources = normalizeText(cell.dataset.matrixCellSourceBlocks || '');
            const factSourceBlocks = new Set(factSources.split(/\s+/).filter(Boolean));
            const expectedSourceUnits = [];
            [
              fact ? (fact.getAttribute('data-source-unit') || '') : '',
              option ? (option.getAttribute('data-source-unit') || '') : '',
            ].forEach(sourceUnit => {
              const sourceBlock = sourceUnit.split(':', 1)[0];
              if (sourceUnit && factSourceBlocks.has(sourceBlock) && !expectedSourceUnits.includes(sourceUnit)) {
                expectedSourceUnits.push(sourceUnit);
              }
            });
            const cellSourceUnits = normalizeText(cell.dataset.matrixCellSourceUnits || '')
              .split(/\s+/).filter(Boolean);
            const reasons = [];
            if (!factId || !fact) reasons.push('fact');
            if (factRef && factRef !== factId) reasons.push('fact-ref');
            if (!targetId || !optionIds.includes(targetId)) reasons.push('target');
            if (orientation === 'facts-as-columns' && rowOptionId !== targetId) reasons.push('row-target');
            if (orientation === 'options-as-columns' && rowFactId !== factId) reasons.push('row-fact');
            if (!visibleText || !declaredText || visibleText !== declaredText) reasons.push('text');
            if (!cellSources || cellSources !== factSources) reasons.push('source-blocks');
            if (cellSourceUnits.join('\u0000') !== expectedSourceUnits.join('\u0000')) reasons.push('source-unit');
            if (seenPairs.has(pair)) reasons.push('duplicate');
            seenPairs.add(pair);
            if (reasons.length) {
              cellIssues.push({ index, fact: factId, target: targetId, reasons });
            }
          });
          const missingPairs = [...expectedPairs].filter(pair => !seenPairs.has(pair));
          const extraPairs = [...seenPairs].filter(pair => !expectedPairs.has(pair));
          if (cellIssues.length || missingPairs.length || extraPairs.length || seenPairs.size !== expectedPairs.size) {
            problems.push({
              reason: 'matrix-cell-coverage', view: viewId, orientation,
              cells: seenPairs.size, expected: expectedPairs.size,
              missingPairs: missingPairs.slice(0, 8),
              extraPairs: extraPairs.slice(0, 8),
              issues: cellIssues.slice(0, 8),
            });
          }
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
  await page.evaluate(() => {
    if (window.setMode) window.setMode('r');
    window.dispatchEvent(new Event('resize'));
  });
  await page.waitForTimeout(260);
  const flowMainPathProblems = await collectFlowMainPathProblems(page);
  const flowDetailDensityProblems = await collectFlowDetailDensityProblems(page);
  const views = await page.$$eval('#paneR section.view', (sections, viewportWidth) => {
    const pane = document.querySelector('#paneR');
    const viewportHeight = pane ? pane.clientHeight : window.innerHeight;
    const round = (value, digits = 2) => Number(value.toFixed(digits));
    return sections.map((view, index) => {
      const isV3 = view.hasAttribute('data-v3-view');
      const flow = view.querySelector(isV3 ? '.mv-diagram' : '[data-flow]');
      const matrix = view.querySelector('.mv-matrix');
      const nodes = [...view.querySelectorAll(isV3 ? '[data-entity-id]' : '.mv-node')]
        .filter(el => el.offsetParent);
      const facts = [...view.querySelectorAll(isV3 ? '[data-fact-id]' : '.mv-fact')]
        .filter(el => el.offsetParent);
      const flowRect = flow && flow.getBoundingClientRect();
      const matrixHeaderCells = matrix ? [...matrix.querySelectorAll('thead tr > *')] : [];
      const matrixColumnWidths = matrixHeaderCells.slice(1).map(cell => cell.getBoundingClientRect().width);
      const nonOverlappingFacts = facts.filter(fact => !fact.closest('.mv-node'));
      const contentArea = [...nodes, ...nonOverlappingFacts].reduce((sum, el) => {
        const rect = el.getBoundingClientRect();
        return sum + rect.width * rect.height;
      }, 0);
      const flowArea = flowRect ? flowRect.width * flowRect.height : 0;
      const mainRegion = view.querySelector('.mv-diagram--architecture .mv-region[data-role=main]');
      const mainRect = mainRegion ? mainRegion.getBoundingClientRect() : null;
      const boundaryTopology = view.querySelector(
        '.mv-diagram--architecture .mv-region--container[data-axis="horizontal"]' +
        '[data-region-columns="3"]:not(:has(>.mv-region-owner)):has(>[data-role=main])',
      );
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
        matrixColumnCount: matrix ? Number(matrix.dataset.columnCount || matrixHeaderCells.length || 0) : 0,
        matrixMinColumnWidth: matrixColumnWidths.length ? round(Math.min(...matrixColumnWidths)) : 0,
        boundaryOrientation: boundaryTopology ? boundaryTopology.dataset.boundaryOrientation || '' : '',
        architectureCompact: boundaryTopology && boundaryTopology.dataset.boundaryOrientation === 'compact',
        naturalMainHeightRatio: boundaryTopology ?
          round(Number(boundaryTopology.dataset.naturalMainHeightRatio || 0), 3) : 0,
        mainHeightRatio: flowRect && mainRect && flowRect.width ? round(mainRect.height / flowRect.width) : 0,
        viewportRatio: viewportHeight ? round(viewHeight / viewportHeight) : 0,
        contentAreaRatio: flowArea ? round(contentArea / flowArea) : 0,
        unitsPerViewport: viewHeight ? round(units * viewportHeight / viewHeight, 1) : 0,
      };
    });
  }, width);
  await page.evaluate(mode => {
    if (window.setMode) window.setMode(mode);
    window.dispatchEvent(new Event('resize'));
  }, originalMode);
  await page.waitForTimeout(180);
  if (flowMainPathProblems.length) {
    throw new Error(
      `[shot] ${width}px 信息重组模式 flow 主路径失败: ` +
      JSON.stringify(flowMainPathProblems.slice(0, 6)),
    );
  }
  if (flowDetailDensityProblems.length) {
    throw new Error(
      `[shot] ${width}px flow 事实轨压过主骨架: ` +
      JSON.stringify(flowDetailDensityProblems.slice(0, 6)) +
      '；请拆出字段/证据视图，主路径只保留决策所需事实',
    );
  }
  return views;
}

async function collectArchitectureBoundaryStates(page) {
  return page.$$eval(
    '.mv-diagram--architecture .mv-region--container[data-axis="horizontal"]' +
    '[data-region-columns="3"]:not(:has(>.mv-region-owner)):has(>[data-role=main])',
    roots => roots.map((root, index) => {
      const view = root.closest('section[data-v3-view]');
      return {
        key: `${view && view.id || 'view'}:${root.dataset.regionId || index}`,
        width: Number(root.getBoundingClientRect().width.toFixed(2)),
        orientation: root.dataset.boundaryOrientation || '',
        reason: root.dataset.boundaryOrientationReason || '',
        naturalRatio: Number(root.dataset.naturalMainHeightRatio || 0),
      };
    }),
  );
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
    const boundsMin = Number(sepAttrs.min);
    const boundsMax = Number(sepAttrs.max);
    const before = Number(await separator.getAttribute('aria-valuenow'));
    await separator.focus();
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(100);
    const afterKey = Number(await separator.getAttribute('aria-valuenow'));
    if (!(afterKey > before)) throw new Error(`[shot] 分隔条 ArrowRight 未增加栏宽: ${before} -> ${afterKey}`);

    const splitBox = await page.locator('[data-md2view-split]').boundingBox();
    const sepBox = await separator.boundingBox();
    if (!splitBox || !sepBox) throw new Error('[shot] 无法读取分隔条几何');
    const dragTarget = Math.max(boundsMin, Math.min(boundsMax, 48));
    await page.mouse.move(sepBox.x + sepBox.width / 2, sepBox.y + sepBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(splitBox.x + splitBox.width * dragTarget / 100, sepBox.y + sepBox.height / 2, { steps: 5 });
    await page.mouse.up();
    await page.waitForTimeout(140);
    const afterDrag = Number(await separator.getAttribute('aria-valuenow'));
    if (Math.abs(afterDrag - dragTarget) > 2) throw new Error(`[shot] 分隔条拖拽未到目标比例: ${afterDrag}% / ${dragTarget}%`);

    await page.reload();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(420);
    const restored = Number(await separator.getAttribute('aria-valuenow'));
    if (Math.abs(restored - afterDrag) > 1) throw new Error(`[shot] 分隔比例未跨刷新恢复: ${afterDrag}% -> ${restored}%`);
    await separator.dblclick();
    await page.waitForTimeout(100);
    const reset = Number(await separator.getAttribute('aria-valuenow'));
    const resetTarget = 42 >= boundsMin && 42 <= boundsMax ? 42 : (boundsMin + boundsMax) / 2;
    if (Math.abs(reset - resetTarget) > 1) throw new Error(`[shot] 双击未恢复默认栏宽: ${reset}% / ${resetTarget}%`);
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

  const architectureRelation = page.locator('.mv-architecture-relation[data-relation-id]:visible').first();
  if (await architectureRelation.count()) {
    await architectureRelation.hover();
    await page.waitForTimeout(100);
    const architectureFocus = await architectureRelation.evaluate(el => {
      const diagram = el.closest('.mv-diagram--architecture');
      const relationId = el.getAttribute('data-relation-id');
      const paths = [...diagram.querySelectorAll('.mv-architecture-wire-path')];
      const matching = paths.filter(path => path.dataset.wireRelationId === relationId);
      return {
        relationId,
        labelActive: el.classList.contains('is-active'),
        matching: matching.length,
        activeMatching: matching.filter(path => path.classList.contains('is-active')).length,
        unmutedOthers: paths.filter(path => path.dataset.wireRelationId !== relationId && !path.classList.contains('is-muted')).length,
      };
    });
    if (!architectureFocus.labelActive || architectureFocus.matching !== 1 ||
        architectureFocus.activeMatching !== 1 || architectureFocus.unmutedOthers) {
      throw new Error(`[shot] 架构关系 hover 高亮范围错误: ${JSON.stringify(architectureFocus)}`);
    }
    await page.mouse.move(1, 1);
    await page.waitForTimeout(80);
  }

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
  // Glyph overhang and fractional CSS pixels can report up to ~4px of scrollWidth
  // even when the painted text is fully inside its box (notably CJK parentheses).
  })).filter(item => item.client > 0 && item.scroll > item.client + 4));
  if (semanticOverflow.length) throw new Error(`[shot] ${width}px 语义文本溢出: ${JSON.stringify(semanticOverflow.slice(0, 4))}`);

  const layoutProblems = await collectLayoutProblems(page);
  if (layoutProblems.length) throw new Error(`[shot] ${width}px 视觉密度布局失败: ${JSON.stringify(layoutProblems.slice(0, 4))}`);

  const factCardStretchProblems = await collectFactCardStretchProblems(page);
  if (factCardStretchProblems.length) {
    throw new Error(
      `[shot] ${width}px 事实卡存在虚假空白拉伸: ` +
      JSON.stringify(factCardStretchProblems.slice(0, 6)),
    );
  }

  const structuralSkeletonProblems = await collectArchitectureStructuralSkeletonProblems(page);
  if (structuralSkeletonProblems.length) {
    throw new Error(
      `[shot] ${width}px architecture 结构骨架失败: ` +
      JSON.stringify(structuralSkeletonProblems.slice(0, 6)),
    );
  }

  const familyProblems = await collectV3FamilyProblems(page);
  if (familyProblems.length) {
    throw new Error(`[shot] ${width}px v3 family 合同失败: ${JSON.stringify(familyProblems.slice(0, 6))}`);
  }

  const firstBoundaryStates = await collectArchitectureBoundaryStates(page);
  await page.waitForTimeout(180);
  const secondBoundaryStates = await collectArchitectureBoundaryStates(page);
  const boundaryProblems = secondBoundaryStates.flatMap(state => {
    const first = firstBoundaryStates.find(candidate => candidate.key === state.key);
    const expected = state.width <= 900 || state.naturalRatio > 0.9 ? 'compact' : 'horizontal';
    const problems = [];
    if (!['compact', 'horizontal'].includes(state.orientation) || state.orientation !== expected) {
      problems.push({ reason: 'architecture-boundary-orientation', expected, ...state });
    }
    if (first && Math.abs(first.width - state.width) <= 2 && first.orientation !== state.orientation) {
      problems.push({
        reason: 'architecture-boundary-orientation-oscillation',
        key: state.key, width: state.width,
        before: first.orientation, after: state.orientation,
      });
    }
    return problems;
  });
  if (boundaryProblems.length) {
    throw new Error(`[shot] ${width}px 架构边界朝向失败: ${JSON.stringify(boundaryProblems.slice(0, 4))}`);
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

async function prepareStableScreenshotState(page, mode = 'viewport') {
  await page.evaluate((mode) => {
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }
    window.scrollTo(0, 0);
    document.documentElement.style.overflowAnchor = 'none';
    document.body.style.overflowAnchor = 'none';
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
    if (left) {
      left.style.overflowAnchor = 'none';
      left.scrollTop = 0;
    }
    if (right) {
      right.style.overflowAnchor = 'none';
      right.scrollTop = 0;
    }

    let stableStyle = document.querySelector('#md2view-stable-shot-style');
    if (!stableStyle) {
      stableStyle = document.createElement('style');
      stableStyle.id = 'md2view-stable-shot-style';
      document.head.appendChild(stableStyle);
    }
    if (mode === 'full-content') {
      stableStyle.textContent = `
        html,body{height:auto!important;overflow:visible!important}
        #split,#split.only-l,#split.only-r{height:auto!important;min-height:calc(100vh - var(--header-h))!important;align-items:start!important}
        .pane{height:auto!important;overflow:visible!important}
        .pane-tag{position:relative!important}
        .hint{display:none!important}
      `;
    } else if (mode === 'semantic-only') {
      stableStyle.textContent = `
      html,body{overflow:visible!important;background:var(--surface-2)!important}
      header.bar,#paneL,.splitter,.hint{display:none!important}
      #split,#split.only-l,#split.only-r{display:block!important;height:auto!important;min-height:0!important}
      #paneR{display:block!important;height:auto!important;overflow:visible!important}
      #paneR .pane-tag{position:relative!important}
      #paneR .doc{max-width:1280px!important;margin:0 auto!important;padding-top:10px!important}
      `;
    } else {
      stableStyle.textContent = '';
    }
  }, mode);
  await page.waitForTimeout(120);
  await page.evaluate(() => {
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }
    window.scrollTo(0, 0);
    const left = document.querySelector('#paneL');
    const right = document.querySelector('#paneR');
    if (left) left.scrollTop = 0;
    if (right) right.scrollTop = 0;
  });
  await page.waitForTimeout(80);
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
            const architectureViewportBudget = width >= 1280 ? 2.2 : width >= 1024 ? 3 : 4;
            if (metric.kind === 'architecture' &&
                metric.viewportRatio > architectureViewportBudget) {
              throw new Error(
                `[shot] ${width}px ${metric.id} architecture-view-exceeds-cognitive-budget: ` +
                `${metric.viewportRatio} > ${architectureViewportBudget} viewports; ` +
                '把总览与局部实现拆成独立视图',
              );
            }
            if (metric.kind === 'architecture' &&
                width >= 1280 &&
                metric.units <= 24 &&
                metric.viewportRatio > 1.5 &&
                metric.contentAreaRatio < 0.40) {
              throw new Error(
                `[shot] ${width}px ${metric.id} architecture-view-wastes-canvas: ` +
                `orientation=${metric.boundaryOrientation || 'n/a'}, ` +
                `naturalMainHeight/rootWidth=${metric.naturalMainHeightRatio}, ` +
                `viewports=${metric.viewportRatio}, ` +
                `contentArea=${(metric.contentAreaRatio * 100).toFixed(0)}%; ` +
                '应调整拓扑、压缩留白或拆图',
              );
            }
            if (metric.kind === 'matrix' &&
                metric.matrixColumnCount >= 8) {
              const matrixColumnBudget = width >= 1280 ? 92 : width >= 1024 ? 84 : 72;
              if (metric.matrixMinColumnWidth > 0 &&
                  metric.matrixMinColumnWidth < matrixColumnBudget) {
                throw new Error(
                  `[shot] ${width}px ${metric.id} matrix-narrow-columns: ` +
                  `${metric.matrixColumnCount} columns, min ` +
                  `${metric.matrixMinColumnWidth}px < ${matrixColumnBudget}px; ` +
                  '请拆分矩阵或改用更合适的图法',
                );
              }
            }
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

        await prepareStableScreenshotState(page, 'viewport');
        await page.screenshot({ path: path.join(cfg.outDir, `viewport-${width}.png`) });
        await prepareStableScreenshotState(page, 'full-content');
        await page.screenshot({ path: path.join(cfg.outDir, `full-${width}.png`), fullPage: true });
        if (cfg.selectors.length) await prepareStableScreenshotState(page, 'semantic-only');
        for (const sel of cfg.selectors) {
          const el = await page.$(sel);
          if (el) {
            await screenshotElementWithFrame(
              page,
              el,
              path.join(cfg.outDir, `${safeName(sel)}-${width}.png`),
            );
          } else {
            failures.push(`${width}px: 显式截图 selector 不存在: ${sel}`);
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
      `${metric.unitsPerViewport} units/viewport, orientation=${metric.boundaryOrientation || 'n/a'}, ` +
      `natural-main=${metric.naturalMainHeightRatio}`);
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
