#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const skillDir = path.resolve(__dirname, "..");
const benchmarkFile = path.join(skillDir, "evals", "benchmark-cases.json");

function parseArgs(argv) {
  const args = {
    benchmark: benchmarkFile,
    format: "md",
    failUnder: null,
    strict: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--benchmark") args.benchmark = argv[++i];
    else if (a === "--gold") args.gold = true;
    else if (a === "--source-prompts") args.sourcePrompts = argv[++i];
    else if (a === "--outputs") args.outputs = argv[++i];
    else if (a === "--case-id") args.caseId = normalizeId(argv[++i]);
    else if (a === "--prompt-file") args.promptFile = argv[++i];
    else if (a === "--init-run") args.initRun = argv[++i];
    else if (a === "--report") args.report = argv[++i];
    else if (a === "--format") args.format = argv[++i];
    else if (a === "--fail-under") args.failUnder = Number(argv[++i]);
    else if (a === "--strict") args.strict = true;
    else if (a === "--help" || a === "-h") args.help = true;
    else throw new Error(`Unknown argument: ${a}`);
  }
  return args;
}

function normalizeId(id) {
  const raw = String(id).trim();
  return /^\d+$/.test(raw) ? raw.padStart(2, "0") : raw;
}

function usage() {
  return `Usage:
  node scripts/eval_prompt_director.mjs --init-run <dir>
  node scripts/eval_prompt_director.mjs --gold [--report report.md]
  node scripts/eval_prompt_director.mjs --case-id 09 --prompt-file prompt.md
  node scripts/eval_prompt_director.mjs --outputs <dir> [--report report.md]

Output files in --outputs can be named 09.md, 09.txt, case-09.md, or JSON with a "prompt" field.
Use --fail-under <score> --strict to make low average scores exit non-zero.`;
}

function hasHardGateFailures(evaluations) {
  return evaluations.some((ev) => ev.hardGatePassed === false);
}

function loadBenchmark(file) {
  const data = JSON.parse(fs.readFileSync(file, "utf8"));
  if (!Array.isArray(data.cases)) throw new Error(`Invalid benchmark file: ${file}`);
  return data;
}

function initRun(dir, benchmark) {
  const root = path.resolve(dir);
  const inputsDir = path.join(root, "inputs");
  const outputsDir = path.join(root, "outputs");
  fs.mkdirSync(inputsDir, { recursive: true });
  fs.mkdirSync(outputsDir, { recursive: true });
  for (const testCase of benchmark.cases) {
    const body = [
      `# Case ${testCase.id}: ${testCase.category}`,
      "",
      `Source: ${testCase.sourceTitle}`,
      "",
      "## Weak Input",
      "",
      testCase.weakInput,
      "",
      "## Expected Capabilities",
      "",
      ...testCase.expectedCapabilities.map((cap) => `- ${cap.text}`),
      "",
      "## Output Instructions",
      "",
      `Generate a complete GPT image2 prompt for the weak input above. Save only the final prompt to ../outputs/${testCase.id}.md.`,
      "",
    ].join("\n");
    fs.writeFileSync(path.join(inputsDir, `${testCase.id}.md`), body, "utf8");
  }
  fs.writeFileSync(path.join(root, "README.md"), [
    "# Prompt Director Eval Run",
    "",
    "Fill `outputs/<case-id>.md` with generated prompts, then run:",
    "",
    "```bash",
    `node ${path.join(skillDir, "scripts", "eval_prompt_director.mjs")} --outputs ${outputsDir} --report ${path.join(root, "report.md")}`,
    "```",
    "",
  ].join("\n"), "utf8");
  return root;
}

const structureChecks = [
  { id: "role", label: "Role positioning", weight: 8, patterns: ["你是", "顶级", "设计师", "总监", "专家", "顾问", "信息架构"] },
  { id: "anti_definition", label: "Anti-plain-task definition", weight: 10, patterns: ["不是普通", "不是简单", "不是模板", "目标不是", "而是"] },
  { id: "input", label: "Input variable", weight: 8, patterns: ["用户输入", "用户最后输入", "输入", "主题", "参考图", "上传"] },
  { id: "plan_first", label: "Understand and plan first", weight: 12, patterns: ["先理解", "先判断", "先.*策划", "在生成前", "智能判断", "自动理解", "内部完成"] },
  { id: "content", label: "Content planning", weight: 12, patterns: ["内容策划", "信息", "条目", "拆解", "提炼", "文案", "说明", "知识点"] },
  { id: "visual", label: "Visual system", weight: 18, patterns: ["构图", "版式", "视觉", "主视觉", "层级", "图文", "配色", "字体", "留白", "阅读路径", "光影", "材质"] },
  { id: "anti_failure", label: "Failure constraints", weight: 12, patterns: ["不要", "避免", "禁止", "不能", "不允许", "廉价", "模板感", "堆字", "跑偏"] },
  { id: "output", label: "Output spec", weight: 8, patterns: ["比例", "画幅", "最终输出", "生成一张", "生成一组", "适合", "可发布", "完成度"] },
  { id: "self_check", label: "Self-check", weight: 6, patterns: ["自检", "检查", "如果.*不满足", "若.*不合格", "重构", "最终标准"] },
  { id: "novice", label: "Novice usability", weight: 6, patterns: ["用户只需要", "可选", "如果用户没有", "自动补全", "无需", "只提供"] },
];

function makeRegex(pattern) {
  return new RegExp(pattern, "i");
}

function hitAny(prompt, patterns) {
  return patterns.some((pattern) => makeRegex(pattern).test(prompt));
}

function scoreStructure(prompt) {
  const checks = structureChecks.map((check) => ({
    id: check.id,
    label: check.label,
    weight: check.weight,
    passed: hitAny(prompt, check.patterns),
  }));
  const score = checks.reduce((sum, check) => sum + (check.passed ? check.weight : 0), 0);
  return { score, checks };
}

function scoreCapabilities(prompt, testCase) {
  const caps = testCase.expectedCapabilities.map((cap) => ({
    id: cap.id,
    text: cap.text,
    passed: hitAny(prompt, cap.patterns || []),
  }));
  const score = caps.length ? Math.round((caps.filter((cap) => cap.passed).length / caps.length) * 100) : 0;
  return { score, caps };
}

function scoreHardGates(prompt, testCase) {
  const gates = testCase.hardGates || {};
  const missingMust = (gates.must || [])
    .filter((gate) => !hitAny(prompt, gate.patterns || []))
    .map((gate) => gate.text);
  const hitMustNot = (gates.mustNot || [])
    .filter((gate) => hitAny(prompt, gate.patterns || []))
    .map((gate) => gate.text);
  return {
    passed: missingMust.length === 0 && hitMustNot.length === 0,
    missingMust,
    hitMustNot,
  };
}

function evaluatePrompt(prompt, testCase) {
  const structure = scoreStructure(prompt);
  const capabilities = scoreCapabilities(prompt, testCase);
  const hardGates = scoreHardGates(prompt, testCase);
  const rawTotal = Math.round(structure.score * 0.65 + capabilities.score * 0.35);
  const total = hardGates.passed ? rawTotal : Math.min(rawTotal, testCase.hardGateFailScore || 69);
  return {
    id: testCase.id,
    category: testCase.category,
    weakInput: testCase.weakInput,
    sourceTitle: testCase.sourceTitle,
    chars: prompt.length,
    structureScore: structure.score,
    capabilityScore: capabilities.score,
    rawTotalScore: rawTotal,
    totalScore: total,
    hardGatePassed: hardGates.passed,
    missingStructure: structure.checks.filter((check) => !check.passed).map((check) => check.label),
    missingCapabilities: capabilities.caps.filter((cap) => !cap.passed).map((cap) => cap.text),
    missingHardGates: hardGates.missingMust,
    hitForbiddenGates: hardGates.hitMustNot,
  };
}

function readPromptFile(file) {
  const text = fs.readFileSync(file, "utf8");
  if (file.endsWith(".json")) {
    const data = JSON.parse(text);
    return String(data.prompt || data.finalPrompt || data.output || "");
  }
  return text;
}

function findOutputForCase(outputsDir, id) {
  const candidates = [
    `${id}.md`,
    `${id}.txt`,
    `${id}.json`,
    `case-${id}.md`,
    `case-${id}.txt`,
    `case-${id}.json`,
  ].map((name) => path.join(outputsDir, name));
  return candidates.find((file) => fs.existsSync(file));
}

function loadGoldPrompts(benchmark, sourcePromptsPath, benchmarkPath) {
  const rawSource = sourcePromptsPath || benchmark.sourcePrompts;
  const source = rawSource && path.isAbsolute(rawSource)
    ? rawSource
    : path.resolve(path.dirname(path.resolve(benchmarkPath)), rawSource || "");
  if (!source) throw new Error("Benchmark does not define sourcePrompts; pass --source-prompts <file>");
  const prompts = JSON.parse(fs.readFileSync(source, "utf8"));
  return new Map(prompts.map((entry, index) => [String(index + 1).padStart(2, "0"), entry.prompt || ""]));
}

function collectEvaluations(args, benchmark) {
  const casesById = new Map(benchmark.cases.map((testCase) => [testCase.id, testCase]));
  const evaluations = [];
  if (args.gold) {
    const gold = loadGoldPrompts(benchmark, args.sourcePrompts, args.benchmark);
    for (const testCase of benchmark.cases) {
      evaluations.push(evaluatePrompt(gold.get(testCase.id) || "", testCase));
    }
    return evaluations;
  }
  if (args.promptFile) {
    if (!args.caseId) throw new Error("--prompt-file requires --case-id");
    const testCase = casesById.get(args.caseId);
    if (!testCase) throw new Error(`Unknown case id: ${args.caseId}`);
    return [evaluatePrompt(readPromptFile(args.promptFile), testCase)];
  }
  if (args.outputs) {
    const outputsDir = path.resolve(args.outputs);
    for (const testCase of benchmark.cases) {
      const file = findOutputForCase(outputsDir, testCase.id);
      if (!file) continue;
      evaluations.push(evaluatePrompt(readPromptFile(file), testCase));
    }
    return evaluations;
  }
  throw new Error("Choose --gold, --prompt-file, --outputs, or --init-run");
}

function summarize(evaluations) {
  const avg = (field) => evaluations.length ? Math.round(evaluations.reduce((sum, ev) => sum + ev[field], 0) / evaluations.length) : 0;
  const byCategory = {};
  for (const ev of evaluations) {
    byCategory[ev.category] ||= [];
    byCategory[ev.category].push(ev);
  }
  return {
    count: evaluations.length,
    averageTotal: avg("totalScore"),
    averageStructure: avg("structureScore"),
    averageCapabilities: avg("capabilityScore"),
    pass80: evaluations.filter((ev) => ev.totalScore >= 80).length,
    needsRepair70: evaluations.filter((ev) => ev.totalScore >= 70 && ev.totalScore < 80).length,
    fail70: evaluations.filter((ev) => ev.totalScore < 70).length,
    byCategory: Object.fromEntries(Object.entries(byCategory).map(([category, values]) => [
      category,
      {
        count: values.length,
        averageTotal: Math.round(values.reduce((sum, ev) => sum + ev.totalScore, 0) / values.length),
      },
    ])),
  };
}

function renderMarkdown(evaluations) {
  const summary = summarize(evaluations);
  const lines = [
    "# GPT image2 Prompt Director Eval Report",
    "",
    `Generated at: ${new Date().toISOString()}`,
    "",
    "## Summary",
    "",
    `- Cases evaluated: ${summary.count}`,
    `- Average total score: ${summary.averageTotal}`,
    `- Average structure score: ${summary.averageStructure}`,
    `- Average capability score: ${summary.averageCapabilities}`,
    `- Pass >= 80: ${summary.pass80}`,
    `- Needs repair 70-79: ${summary.needsRepair70}`,
    `- Fail < 70: ${summary.fail70}`,
    "",
    "## Category Averages",
    "",
    ...Object.entries(summary.byCategory).map(([category, value]) => `- ${category}: ${value.averageTotal} (${value.count} cases)`),
    "",
    "## Case Results",
    "",
  ];
  for (const ev of evaluations) {
    lines.push(`### ${ev.id}. ${ev.category} - ${ev.totalScore}`);
    lines.push("");
    lines.push(`Source: ${ev.sourceTitle}`);
    lines.push("");
    lines.push(`Weak input: ${ev.weakInput}`);
    lines.push("");
    lines.push(`Scores: structure ${ev.structureScore}, capabilities ${ev.capabilityScore}, chars ${ev.chars}`);
    if (ev.missingStructure.length) {
      lines.push("");
      lines.push(`Missing structure: ${ev.missingStructure.join("; ")}`);
    }
    if (ev.missingCapabilities.length) {
      lines.push("");
      lines.push("Missing capabilities:");
      for (const cap of ev.missingCapabilities) lines.push(`- ${cap}`);
    }
    if (!ev.hardGatePassed) {
      lines.push("");
      lines.push(`Hard gates: failed (raw score ${ev.rawTotalScore} capped to ${ev.totalScore})`);
      if (ev.missingHardGates.length) {
        lines.push("");
        lines.push("Missing hard gates:");
        for (const gate of ev.missingHardGates) lines.push(`- ${gate}`);
      }
      if (ev.hitForbiddenGates.length) {
        lines.push("");
        lines.push("Forbidden gates hit:");
        for (const gate of ev.hitForbiddenGates) lines.push(`- ${gate}`);
      }
    }
    lines.push("");
  }
  return lines.join("\n");
}

function writeOutput(text, args) {
  if (args.report) {
    fs.mkdirSync(path.dirname(path.resolve(args.report)), { recursive: true });
    fs.writeFileSync(args.report, text, "utf8");
  } else {
    process.stdout.write(text + "\n");
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    return;
  }
  const benchmark = loadBenchmark(args.benchmark);
  if (args.initRun) {
    const dir = initRun(args.initRun, benchmark);
    console.log(JSON.stringify({ initRun: dir, cases: benchmark.cases.length }, null, 2));
    return;
  }
  const evaluations = collectEvaluations(args, benchmark);
  const summary = summarize(evaluations);
  const output = args.format === "json" ? JSON.stringify({ summary, evaluations }, null, 2) : renderMarkdown(evaluations);
  writeOutput(output, args);
  if (args.strict && ((args.failUnder != null && summary.averageTotal < args.failUnder) || hasHardGateFailures(evaluations))) {
    process.exitCode = 1;
  }
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
