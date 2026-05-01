#!/usr/bin/env bash
# Harness Worker+Reviewer Loop — 持续领取任务、修复、审查、commit
# 用法:
#   ./sf-worker-reviewer.sh          # 单次循环（领一个任务）
#   ./sf-worker-reviewer.sh --loop   # 持续循环直到没有可做的任务
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKER_PROMPT="$SCRIPT_DIR/prompts/worker.md"
REVIEWER_PROMPT="$SCRIPT_DIR/prompts/reviewer.md"

# 用户额外上下文（从临时文件读取）
USER_CONTEXT=""
if [ -f /tmp/harness-context.txt ]; then
  USER_CONTEXT="$(cat /tmp/harness-context.txt)"
fi

cd "$PROJECT_DIR"

LOOP_MODE=false
if [[ "${1:-}" == "--loop" ]]; then
  LOOP_MODE=true
fi

# 构建用户额外上下文段落（如果有）
EXTRA_PROMPT=""
if [ -n "$USER_CONTEXT" ]; then
  EXTRA_PROMPT="

## 用户本轮额外指令

${USER_CONTEXT}

请在工作时参考用户的额外指令。"
fi

# 检查 TODO.md 中是否有可做的任务（[待领取] 或 [被拒绝]）
has_work() {
  grep -qE '^\s*-\s*\[[ x]\]\s*\[(待领取|被拒绝)\]' TODO.md 2>/dev/null
}

run_worker() {
  echo "=== Worker starting at $(date) ==="

  # 读取必读文档，注入上下文
  WORKER_DOCS=""
  for doc in "CLAUDE.md" "TODO.md"; do
    if [ -f "$doc" ]; then
      WORKER_DOCS="${WORKER_DOCS}

---
### ${doc}
$(cat "$doc")
"
    fi
  done

  claude -p "$(cat "$WORKER_PROMPT")

项目路径: $PROJECT_DIR
当前时间: $(date '+%Y-%m-%d %H:%M:%S')

以下是必读文档的内容：

${WORKER_DOCS}
${EXTRA_PROMPT}

请从 TODO.md 中领取最高优先级的 [待领取] 或 [被拒绝] 任务并完成修复。

关键提醒：
1. 不要执行 git commit——这是 Reviewer 的职责
2. 每次只做一个任务
3. 测试必须通过才能标记 [待审查]
4. 单元测试通过后，必须尝试端到端验证（sf run），记录 e2e 结果
5. 严格按照任务状态机操作：[待领取] → [进行中] → [待审查]" \
    --permission-mode bypassPermissions \
    --output-format stream-json 2>&1 | tail -3

  echo "=== Worker finished at $(date) ==="
}

run_reviewer() {
  echo "=== Reviewer starting at $(date) ==="

  # 读取 TODO.md（最新状态）和相关文档
  REVIEWER_DOCS=""
  for doc in "CLAUDE.md" "TODO.md"; do
    if [ -f "$doc" ]; then
      REVIEWER_DOCS="${REVIEWER_DOCS}

---
### ${doc}
$(cat "$doc")
"
    fi
  done

  claude -p "$(cat "$REVIEWER_PROMPT")

项目路径: $PROJECT_DIR
当前时间: $(date '+%Y-%m-%d %H:%M:%S')

以下是相关文档的内容：

${REVIEWER_DOCS}
${EXTRA_PROMPT}

Worker 刚完成了任务。请审查 Worker 的改动，更新 TODO.md。

关键提醒：
1. 用 git status 和 git diff 查看改动（Worker 不会 commit）
2. 通过：移入 Done Log + 执行 git commit
3. 不通过：标记 [被拒绝] + 写清楚 issues 和 suggestion
4. 同一任务失败 3 次后标记为 blocked" \
    --permission-mode bypassPermissions \
    --output-format stream-json 2>&1 | tail -3

  echo "=== Reviewer finished at $(date) ==="
}

# 主循环
iteration=0
while true; do
  iteration=$((iteration + 1))
  echo ""
  echo "============================================"
  echo "  Iteration #${iteration} at $(date)"
  echo "============================================"

  # 检查是否有可做的任务
  if ! has_work; then
    echo "No actionable tasks found (no [待领取] or [被拒绝] in TODO.md)."
    echo "Waiting for Inspector to add new tasks."
    break
  fi

  # Phase 1: Worker
  run_worker

  # 检查 Worker 是否真的完成了任务
  if ! grep -q "\[待审查\]" TODO.md 2>/dev/null; then
    echo "Worker did not complete any task. Skipping review."
    if [[ "$LOOP_MODE" == "false" ]]; then
      break
    fi
    continue
  fi

  # Phase 2: Reviewer
  run_reviewer

  echo "=== Iteration #${iteration} complete ==="

  # 单次模式：做完一轮就退出
  if [[ "$LOOP_MODE" == "false" ]]; then
    break
  fi

  # 循环模式：短暂休息后继续
  echo "Waiting 5 seconds before next iteration..."
  sleep 5
done

echo ""
echo "=== Worker+Reviewer session ended at $(date) ==="
echo "Total iterations: ${iteration}"
