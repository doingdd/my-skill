# git-push-guard

纯 hook 插件（无 skill）：拦截 AI 直推共享默认分支 master/main，弹出确认（ask）而非硬禁止——共享项目引导走分支+MR，个人/小型项目确认后放行。

## 拦截范围

- `git push origin master` / `git push origin main`（显式目标）
- `git push origin xxx:master`（refspec 形式）
- 当前分支就是 master/main 时的裸 `git push`

## 按仓库永久放行

不想每次确认的仓库，把其根目录绝对路径加入白名单（一行一个，支持 `#` 注释）：

```bash
mkdir -p ~/.claude/hooks
echo "/path/to/your/repo" >> ~/.claude/hooks/push-default-branch-allowlist.txt
```

白名单内的仓库直推默认分支静默放行；文件不存在时所有仓库都会询问。

## 依赖

- `jq`（解析 hook 输入）
- `git`
