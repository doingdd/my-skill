#!/bin/bash
# 用法: scaffold.sh <hook 脚本路径> [输出目录]
# 生成行为矩阵测试骨架：run/assert 协议 + 2 个 TODO 场景。已知 bash 坑位预修，勿改协议。

set -euo pipefail

[ $# -ge 1 ] || { echo "用法: scaffold.sh <hook 脚本路径> [输出目录]" >&2; exit 1; }
HOOK_INPUT=$1
[ -f "$HOOK_INPUT" ] || { echo "✗ hook 脚本不存在: $HOOK_INPUT" >&2; exit 1; }
HOOK_ABS=$(cd "$(dirname "$HOOK_INPUT")" && pwd)/$(basename "$HOOK_INPUT")
HOOK_NAME=$(basename "$HOOK_ABS")
HOOK_NAME=${HOOK_NAME%.*}
OUT_DIR=${2:-$(dirname "$HOOK_ABS")}
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/test_${HOOK_NAME}.sh"
chmod +x "$HOOK_ABS"

cat > "$OUT" <<HEREDOC
#!/bin/bash
# ${HOOK_NAME} 行为测试骨架——由 hook-test-kit 生成。
# 断言协议：EMPTY = 输出必须为空；!pattern = 必须不命中；其余 = egrep 必须命中。
# TODO: 按被测 hook 的语义替换 HOOK_INPUT、stdin JSON 与场景。

set -u
HOOK="$HOOK_ABS"
WORK="\$(mktemp -d)"
trap 'rm -rf "\$WORK"' EXIT

pass=0; fail=0
run() { # run <名称> <cwd> <stdin JSON> <断言...>
  local label="\$1" dir="\$2" payload="\$3"; shift 3
  local out rc a good=1
  out=\$(cd "\$dir" && printf '%s' "\$payload" | bash "\$HOOK" 2>/dev/null); rc=\$?
  for a in "\$@"; do
    if [ "\$a" = EMPTY ]; then
      if [ \$rc -ne 0 ] || [ -n "\$out" ]; then echo "✗ \${label} 期望放行(空输出) 实得 rc=\$rc out=\${out:0:80}"; good=0; fi
      continue
    fi
    if [ "\${a#!}" != "\$a" ]; then
      if printf '%s' "\$out" | grep -qE "\${a#!}"; then echo "✗ \${label} 不应命中 [\${a#!}]"; good=0; fi
    elif ! printf '%s' "\$out" | grep -qE "\$a"; then
      echo "✗ \${label} 断言未命中 [\$a] 实得: \$(printf '%s' "\$out" | head -1)"; good=0
    fi
  done
  if [ "\$good" = 1 ]; then echo "✓ \${label}"; pass=\$((pass+1)); else fail=\$((fail+1)); fi
}

# TODO 场景 1：快速门——非 hook 目标输入应放行
run "非目标输入放行" "\$WORK" '{}' EMPTY

# TODO 场景 2：主路径——按 hook 语义填入真实 payload 与断言
# run "示例拦截" "\$WORK" '{"tool_input":{"command":"..."},"cwd":"..."}' 'permissionDecision' '预期文案片段'

echo "── 通过 \$pass / 失败 \$fail"
[ "\$fail" -eq 0 ]
HEREDOC

chmod +x "$OUT"
echo "✓ 已生成 $OUT"
echo "  下一步：按被测 hook 语义填场景；全绿后做变异实验（每条拦截规则改坏必须变红）。"
