---
name: x-article-download
description: 下载 X/Twitter 内容为本地 Markdown，支持单条推文（长文/图片/视频/GitHub 仓库）和整账号批量下载。自动判断内容类型执行对应策略。
version: 4.0.0
author: doing
metadata:
  hermes:
    tags: [X, Twitter, 下载, Article, Markdown, 图片, 视频, 逐字稿, Whisper, GitHub, clone, 批量下载, 整账号, xreach, 提示词]
    category: media
---

# X 内容下载器

将 X/Twitter 内容自动分类下载。支持：
- **单条推文**：纯文字+图片、视频+转录、GitHub 仓库推荐帖
- **整账号批量下载**：获取某账号所有推文、批量下载图片、提取结构化内容

## 触发条件

- 用户发送 `x.com/xxx/status/xxx` 或 `x.com/xxx/article/xxx` 链接 → 路径 A/B/C
- 用户发送 `x.com/xxx` 或 `@xxx` 账号链接，要求下载"所有内容" → 路径 D
- 用户说"下载这篇文章/视频"、"存下来"且链接是 X 的 → 路径 A/B/C
- 用户说"下载这个账号所有推文/图片/提示词" → 路径 D

## 前置依赖

| 工具 | 用途 | 安装检查 |
|------|------|---------|
| xreach (agent-reach) | 批量获取推文、分页 | `which xreach` |
| yt-dlp | 视频/推文信息获取、视频下载 | `which yt-dlp` |
| whisper (openai-whisper) | 语音转文字 | `which whisper` |
| ffmpeg | 音频提取 | `which ffmpeg` |
| git | GitHub 仓库 clone | `which git` |

---

## 第零步：内容类型检测（必做，优先于一切）

**在执行任何下载操作之前，先用浏览器打开推文，提取正文文本，判断内容类型。**

### 0.1 打开推文 + 提取文本

```
browser_navigate → url = {用户给的链接}
```

用 `browser_console` 提取正文和所有链接：

```javascript
const article = document.querySelector('article[data-testid="tweet"]');
if (article) {
  const text = article.innerText;
  const links = Array.from(article.querySelectorAll('a[href]')).map(a => a.href);
  JSON.stringify({ text: text.substring(0, 10000), links });
} else { JSON.stringify({ text: '', links: [] }); }
```

### 0.2 判断逻辑

根据提取到的文本和链接，按以下规则判断：

| 条件 | 类型 | 执行路径 |
|------|------|---------|
| 文本中包含 ≥1 个 `github.com/xxx/xxx` 仓库链接 **且** 帖子主题是推荐/介绍工具库 | **GitHub 推荐帖** | → 执行 **路径 C** |
| yt-dlp 检测到视频（有 duration/vcodec） | **视频帖** | → 执行 **路径 B** + 路径 A 的文本提取 |
| 推文引用了 `x.com/i/article/xxx`（X Article），text 中无代码块 | **Article 引用帖** | → 记录，但**跳过 Article 内容**（Article 需登录）；xreach text 的描述性文字作为参考 |
| 推文引用了 `x.com/i/article/xxx`，且 text 中有代码块 | **含提示词的 Article 相关帖** | → 执行 **路径 A**，代码块就是提示词 |
| 以上都不满足 | **纯文字帖** | → 执行 **路径 A** |

**重要区分**：
- `x.com/i/article/xxx` = X Article（长文格式，需要登录，xreach 没有 Article API）
- 推文 Quote Tweet 引用 Article 时，xreach text 只显示 Quote 部分（标题+摘要），不是 Article 全文
- **正确策略**：遇到 Article 引用帖，直接跳过；遍历账号全部推文，靠其他有代码块的推文来获取真实提示词（而不是死磕 Article）

**GitHub 推荐帖的识别信号：**
- 文本中出现 1 个以上 `github.com/owner/repo` 格式链接
- 关键词：开源、GitHub、工具、推荐、仓库、clone、star、fork
- 帖子核心目的是推荐工具/库，而非讨论某个库的 issue 或 PR

**注意**：如果帖子只有 1 个 GitHub 链接且内容是讨论 issue/PR/代码片段，不属于 GitHub 推荐帖，走路径 A。

---

## 路径 A：纯文字 + 图片（默认路径）

### 第 1 步：提取完整正文

用 `browser_console` 提取正文（可能需要滚动拼接）：

```javascript
const article = document.querySelector('article[data-testid="tweet"]');
if (article) {
  article.innerText.substring(0, 30000);
} else { 'No article found'; }
```

如果文本被截断，`browser_scroll` 向下滚动后再抓一次，拼接。

**如果是英文内容**：翻译成中文。将原文分段（每段 ≤2000 字），逐段翻译后合并。翻译风格保持口语化，专业术语保留英文原文加括号注释。

### 第 2 步：提取图片 URL

```javascript
const imgs = document.querySelectorAll('img');
const results = [];
imgs.forEach(img => {
  if (img.src && img.src.includes('twimg') && !img.src.includes('profile_images')) {
    results.push(img.src);
  }
});
JSON.stringify(results);
```

过滤掉 `profile_images`（头像），只保留 `media` 图片。如果图片 URL 含 `format=png`，保持原格式。

### 第 3 步：下载图片到本地

```bash
curl -sL -o "{output_dir}/images/{序号}-{描述}.jpg" "{img_url}?format=jpg&name=large"
```

### 第 4 步：组装 Markdown

创建目录结构：
```
<OUTPUT_DIR>/{清理后的标题}/
├── {清理后的标题}.md
└── images/
    ├── 01-xxx.jpg
    └── ...
```

Markdown 内容：
- 文件头加元信息（作者、日期、原文链接）
- 在对应位置插入 `![描述](images/xx-xxx.jpg)`
- 如果原文是英文，正文使用中文翻译，文末附上英文原文

---

## 路径 B：视频下载 + 转录 + 翻译

### 第 5 步：检测视频

```bash
yt-dlp --flat-playlist -j "{url}" 2>&1 | head -5
```

检查 `"duration"` 和 `"vcodec"` 字段。有视频则继续。

### 第 6 步：下载视频

优先使用 HTTP 直链（避免 HLS 极慢问题）：

```bash
# 1. 获取 HTTP 格式直链
yt-dlp -j --no-playlist "{url}" 2>/dev/null | python3 -c "
import sys, json
info = json.load(sys.stdin)
for f in info.get('formats', []):
    if 'http-' in f.get('format_id','') and f.get('vcodec','none') != 'none':
        print(f\"{f['format_id']}: {f['url']}\")
"

# 2. curl 下载
curl -L -o video_silent.mp4 "{http_url}"
```

如果找不到 HTTP 直链：
```bash
yt-dlp -f "http-832" --no-playlist -o "video.%(ext)s" "{url}"
```

最后的退路：
```bash
yt-dlp -f "bestvideo[height<=720]+bestaudio/best[height<=720]/best[height<=720]" \
  -o "{output_dir}/videos/video.mp4" --continue "{url}"
```

**大视频务必用 `background=true` + `notify_on_complete=true`**

### 第 7 步：提取音频 + Whisper 转录

```bash
ffmpeg -i "{output_dir}/videos/video.mp4" -vn -acodec pcm_s16le -ar 16000 -ac 1 "{output_dir}/videos/audio.wav" -y

whisper "{output_dir}/videos/audio.wav" --model medium --output_format all --output_dir "{output_dir}/transcripts" --verbose False
```

**模型选择**：`base` 快但中文差，`medium` 平衡（推荐），`large` 最准但慢。长视频（>20min）用 `background=true`。

### 第 8 步：翻译（如果是英文）

1. 读取 `transcripts/audio.txt`
2. 分段翻译成中文（每段 ≤2000 字）
3. 生成 `transcripts/audio-zh.md`

### 第 9 步：组装输出

```
{output_dir}/
├── {标题}.md
├── images/
├── videos/
│   └── video.mp4
├── transcripts/
│   ├── audio.txt
│   ├── audio.srt
│   └── audio-zh.md（英文视频才有）
└── transcript.md
```

---

## 路径 C：GitHub 仓库推荐帖

### 第 10 步：提取所有 GitHub 仓库 URL

从第零步提取的文本和链接中，用正则匹配所有 GitHub 仓库地址：

```
github.com/[\w.-]+/[\w.-]+
```

**注意**：
- 过滤掉非仓库页面（如 `github.com/features`、`github.com/topics` 等）
- 过滤掉指向 issue/PR/pull/releases 的链接（只保留仓库根路径）
- 对于 t.co 短链接，先 `curl -sI -L` 解析真实地址
- 去重

### 第 11 步：确认数量

| 仓库数量 | 操作 |
|----------|------|
| 1-5 个 | 直接 clone，无需确认 |
| >5 个 | 用 `clarify` 列出仓库名和简介，让用户选择要 clone 哪些 |

### 第 12 步：批量 clone

默认 clone 到 `~/repos/` 目录：

```bash
mkdir -p ~/repos
cd ~/repos
git clone https://github.com/{owner}/{repo}.git
```

逐个 clone，避免并行（`&` 在 foreground terminal 不可用）。如果仓库数量多，可以写临时脚本用 `background=true` 后台批量执行。

### 第 13 步：报告结果

clone 完成后，输出汇总表格：

```
| # | 仓库 | 简介 |
|---|------|------|
| 1 | owner/repo | 一句话描述 |
```

如果部分 clone 失败，单独列出失败的仓库和原因。

**路径 C 不需要生成 Markdown 文件，只需要 clone 仓库。** 如果用户同时要求"存下来"或"做笔记"，额外走路径 A 保存推文文本。

---

## 已验证有效的路径

| 步骤 | 方法 | 状态 |
|------|------|------|
| xreach 认证 | `xreach auth extract --browser chrome` | ✅ 有效 |
| 批量获取推文 | `xreach tweets @user --json -n 100` + cursor 分页 | ✅ 有效（9页→122条） |
| xreach text 含代码块 | 代码块保留完整 | ✅ 真实提示词 |
| xreach text 无代码块 | 只有描述性文字，Article 需登录 | ⚠️ 需浏览器补全或跳过 |
| r.jina.ai 批量 100+ 条 | SSL EOF 100% 失败 | ❌ 不适合批量 |
| 检测视频 | yt-dlp --flat-playlist -j 检查 duration/vcodec | ✅ 有效 |
| 获取正文 | browser_navigate + browser_console(`article.innerText`) | ✅ 有效 |
| 获取图片 URL | xreach `media[].url` 直接给出高清 URL | ✅ 优于浏览器提取 |
| **Article 类型图片** | **r.jina.ai 解析推文 → 提取 pbs.twimg.com URL → Bearer Token 下载** | ✅ **88/88 成功（2026-05-09 实测）** |
| 下载图片 | urllib 或 curl，ThreadPoolExecutor(max_workers=8) | ✅ 93/99 成功 |
| 下载视频 | yt-dlp HLS m3u8 合并 | ✅ 有效 |
| 提取音频 | ffmpeg -i video.mp4 -vn -ar 16000 audio.wav | ✅ 有效 |
| 语音转录 | whisper --model medium audio.wav | ✅ 有效 |
| 组装 Markdown | write_file 相对路径引用 | ✅ 有效 |
| GitHub clone | git clone 到 ~/repos/ | ✅ 有效 |
| t.co 解析 | curl -sI -L 查看最终 Location | ✅ 有效 |

## 无效的方法（不要再试）

| 方法 | 为什么不行 |
|------|-----------|
| xreach tweet 获取 Article 内容 | xreach 没有 Article API，只返回推文正文 |
| curl + cookies 请求 Article | 返回的是需要 JS 渲染的 HTML，无法提取内容 |
| r.jina.ai 批量提取 | 批量请求 100+ 条时 100% SSL EOF 错误，只适合单条验证 |

## 边界情况

- 文本太长一次抓不全 → 滚动后多次抓取拼接
- 图片 URL 带 `profile_images` → 头像，跳过
- 图片 URL 含 `format=png` → 保持原格式
- 视频很大（>300MB）→ `background=true`
- 视频很长（>30min）→ whisper 用 `background=true`
- GitHub 推荐帖中 t.co 短链需要先解析 → `curl -sI -L`
- GitHub 推荐帖配图中有仓库地址截图 → 用 vision_analyze 识别
- 帖子同时有 GitHub 链接和视频 → 按主体意图判断，优先走 GitHub 路径
- 仓库已存在 → `git pull` 更新而非重新 clone
- 纯英文文字帖 → 翻译成中文，文末附英文原文

## 路径 D：整账号批量下载

当用户要求下载某个 X 账号的**所有内容**（所有推文、所有图片、提示词等）时走此路径。

> 📖 **详细案例**：`references/x-tweet-structure-patterns.md` 包含推文结构模式分析和 @xiaoxiaodong01 的实际案例。
> 📖 **@xiaoxiaodong01 提取模式**：`references/xiaoxiaodong01-extraction-patterns.md` 包含该账号提示词提取的实战经验、t.co 遮蔽问题解决方案和已知推文映射。

**⚠️ 前置沟通（重要）**：
开始批量下载前，先检查账号的推文结构。如果发现大量推文引用 Article，**立即告知用户**：
- Article 内容需要登录才能查看
- 能提取的是：推文正文、代码块、佐料、图片
- 不能提取的是：Article 中的完整提示词/汤底
- 让用户决定是否继续，或者提供登录凭据

不要等下载完了才说"需要登录"——这会让用户觉得浪费了时间。

### 前置依赖

| 工具 | 用途 | 安装检查 |
|------|------|---------|
| xreach (agent-reach) | 批量获取推文 | `which xreach` |
| requests (Python) | 批量下载图片 | `python3 -c "import requests"` |
| browser-cookie3 | 从浏览器提取认证 | `pip3 install browser-cookie3` |

### 第 14 步：认证 xreach

**必须先认证，否则返回 "Not authenticated"。**

```bash
# 从本地 Chrome 浏览器自动提取 Twitter cookies
xreach auth extract --browser chrome
```

验证：
```bash
xreach auth check
```

> ⚠️ 如果 `xreach auth extract` 报错 "browser_cookie3 not installed"，先 `pip3 install browser-cookie3`。
> 如果用户没有在 Chrome 登录 Twitter，需要手动设置：`xreach auth set --auth-token <token> --ct0 <token>`

### 第 15 步：获取全部推文（带分页）

```python
import json, subprocess

def get_all_tweets(username, max_pages=50):
    all_tweets = []
    cursor = None
    for page in range(1, max_pages + 1):
        cmd = f'xreach tweets @{username} --json -n 100'
        if cursor:
            cmd += f' --cursor {cursor}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        data = json.loads(result.stdout)
        items = data.get('items', [])
        if not items:
            break
        all_tweets.extend(items)
        cursor = data.get('cursor')
        if not data.get('hasMore') or not cursor:
            break
    return all_tweets
```

**关键字段**：
- `items[].text` — 推文正文
- `items[].media[].url` — 图片 URL（pbs.twimg.com）
- `items[].id` — 推文 ID
- `cursor` — 分页游标
- `hasMore` — 是否还有更多

### 第 16 步：批量下载图片（并发）

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests, os

def download_image(url, filepath):
    try:
        r = requests.get(url + '?format=jpg&name=large', timeout=30)
        r.raise_for_status()
        with open(filepath, 'wb') as f:
            f.write(r.content)
        return True
    except:
        return False

# 5 并发，100+ 张图通常 2-3 分钟完成
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(download_image, url, path): url for url, path in tasks}
    for f in as_completed(futures):
        f.result()
```

**命名规则**：`{tweet_id}_{序号}.{ext}`，确保唯一且可回溯到原始推文。

### 第 17 步：组装账号级输出

```
{output_dir}/
├── README.md                    # 总览：统计、分类、使用建议
├── {主题}整理.md                # 按分类整理的文档
├── 具体内容提取.md              # 提取的结构化内容（提示词/观点/工具等）
├── 图片索引.md                  # 按推文ID分组的图片索引
├── 目录结构说明.md
├── tweets_raw.json              # 原始推文数据
├── filtered_tweets.json         # 筛选后的推文数据
└── images/
    └── {tweet_id}_{序号}.jpg
```

### 第 18 步：内容提取与分类

根据用户需求，从推文文本中提取特定内容：

```python
import re

# 示例：提取提示词相关内容
keywords = ['提示词', 'prompt', 'GPT2', 'GPT-2', 'image2']
filtered = [t for t in tweets if any(kw in t['text'] for kw in keywords)]

# 按主题分类
categories = {}
for tweet in filtered:
    text = tweet['text'].lower()
    if '情头' in text:
        categories.setdefault('情头', []).append(tweet)
    elif '封面' in text:
        categories.setdefault('封面', []).append(tweet)
    # ... 更多分类
```

**重要**：xreach 返回的 `text` 字段会被截断，需要浏览器提取完整内容才能获取代码块和长文本。详见第 19 步。

### 已验证有效

| 步骤 | 方法 | 状态 |
|------|------|------|
| xreach 认证 | `xreach auth extract --browser chrome` | ✅ 有效 |
| 获取推文 | `xreach tweets @user --json -n 100` | ✅ 有效 |
| 分页 | cursor 字段 + `--cursor` 参数 | ✅ 有效 |
| 并发图片下载 | ThreadPoolExecutor(max_workers=5) | ✅ 有效（100+ 张 < 3min） |
| 图片命名 | `{tweet_id}_{序号}.{ext}` | ✅ 有效 |

### 路径 D 新增的坑

| 问题 | 解决 |
|------|------|
| `xreach tweets` 返回 "Not authenticated" | 先 `xreach auth extract --browser chrome` |
| `browser_cookie3 not installed` | `pip3 install browser-cookie3` |
| 图片下载 SSL EOF 错误 | 个别图片失败正常，重试或跳过 |
| Python execute_code 超时（300s） | 用 `terminal` 跑 Python 脚本，不要用 execute_code |
| `requests` 的 SSL 警告 | 忽略，不影响下载 |
| **xreach text 字段被截断** | **长推文、代码块会丢失，必须用浏览器提取完整内容** |
| **Twitter Article 需要登录** | **`x.com/i/article/xxx` 需要登录，未登录只显示登录页** |
| **t.co 链接遮住真实外部 URL** | **推文里的 t.co 短链接可能指向微信/公众号文章，但 xreach 的 text 字段和 API 都只显示 t.co 本身，无法看到穿过重定向后的真实地址。应对：先 `curl -sI -L https://t.co/xxx` 解析真实 URL，或用浏览器打开推文从页面提取完整链接** |
| **X Tweet 引用微信公众号文章** | **推文说"提示词在文章里"且文章是 mp.weixin.qq.com → 立即加载 `wechat-article-md-local` skill，而不是尝试用 xreach 或 r.jina.ai 提取。xreach 没有微信公众号 API** |
| **浏览器批量访问被风控** | **连续访问 10+ 个 X 页面会被识别为机器人，出现 stealth_warning、超时、CAPTCHA。应对：每次请求间隔 3-5 秒，分批次操作，或改用 xreach CLI** |
| **Article 类型推文图片** | **推文引用 Article 时，图片不在 tweet media 数组里，在 Article 页面。xreach 返回 `media: []`。解决：r.jina.ai 解析 Article markdown → 提取图片 URL → curl + Bearer Token 下载。** | ✅ 2026-05-09 实测 88 张全成功 |
| **Twitter 图片 403** | **直接 curl pbs.twimg.com 会 403。解决：加 `-H "Authorization: Bearer AAAA...gDZ"` 头。注意：URL 中的 `?format=jpg&name=small` 等参数必须保留。** | ✅ 2026-05-09 实测 |
| **xreach 没有 Article API** | **xreach tweet 命令不返回 Article 内容，只返回推文正文。Article 内容只能通过 r.jina.ai 或浏览器获取** | ⚠️ 已知限制 |

### 第 19 步：提取完整推文内容（重要！）

**xreach 返回的 `text` 字段会被截断**，特别是：
- 包含代码块（` ``` `）的推文
- 超过 280 字符的长推文
- 引用 Twitter Article 的推文

**必须用浏览器提取完整内容**：

```python
# 需要提取完整内容的推文ID列表
tweet_ids = ['2051854592732991621', '2050042358297989436', ...]

# 对每个推文：
# 1. browser_navigate → https://x.com/xiaoxiaodong01/status/{tweet_id}
# 2. browser_console 提取完整文本
```

```javascript
// browser_console 提取完整推文文本
const tweetArticle = document.querySelector('article[data-testid="tweet"]');
if (tweetArticle) {
    tweetArticle.innerText;
} else {
    'No article found';
}
```

**提取代码块内容**：

```python
import re

# 从完整文本中提取代码块
code_blocks = re.findall(r'```(.*?)```', text, re.DOTALL)
# code_blocks[0] 就是提示词内容
```

**识别需要浏览器提取的推文**：

```python
# 包含代码块的推文（xreach text 会被截断）
tweets_with_code = [t for t in tweets if '```' in t.get('text', '')]

# 包含 t.co 链接的推文（可能引用 Article）
tweets_with_tco = [t for t in tweets if 't.co/' in t.get('text', '')]
```

### 第 19b 步：r.jina.ai 优先提取 Article 内容（优化）

**对于 Article 格式推文，优先用 r.jina.ai 提取，比浏览器更快且能获取图片 alt text**：

```bash
curl -s "https://r.jina.ai/https://x.com/xiaoxiaodong01/status/{tweet_id}" \
  -H "Accept: text/markdown"
```

**判断标准**：

| r.jina.ai 读到内容 | 类型 | 继续方案 |
|-------------------|------|---------|
| `## Post` + 正文 > 500 chars | Article 格式 | ✅ 有效，直接用 |
| 只有 "Quote" + 标题 | Quote Tweet | ❌ 降级到浏览器 |
| "Login" 或 "Sign up" | 需要登录 | ❌ 记录，告知用户 |

**提取图片 alt text（提示词常在这里）**：

```python
import re
all_alts = re.findall(r'Image (\d+): ([^\]]{10,})', content)
prompt_keywords = ['任务', '结构要求', '角色要求', '生成', '风格', '提示词', '简单来说']
for idx, alt in all_alts:
    if any(kw in alt for kw in prompt_keywords):
        print(f"Found prompt in Image {idx}: {alt[:200]}")
```

**实战验证**：
- ✅ 推文 `2051854592732991621`（情头）→ r.jina.ai 读到完整正文 + "Image 6: 简单来说，先垫图你喜欢的图片..." → 提示词成功提取
- ❌ 推文 `2051898673395822760`（小东东技巧 x 贰）→ isQuote=true，r.jina.ai 只读到"Quote"标题 → 需浏览器

**工作流优化**：

```
推文 ID → r.jina.ai 提取
    ├── 读到完整 Article 内容 + 图片 alt
    │   └── alt 包含提示词关键词 → 直接使用 ✅
    ├── 只读到 Quote 标题
    │   └── 降级到浏览器提取（且可能仍需登录）⚠️
    └── 读到登录页
        └── 标记为"需登录"，告知用户 🔒
```

### 第 20 步：Twitter Article 内容提取

**Twitter Article（`x.com/i/article/xxx`）需要登录才能查看**。

从推文中可以看到引用的文章标题和摘要，但完整内容需要登录：

```python
# 从浏览器提取的文章摘要
# 文章标题：GPT2：万物皆情头 x 情头秘籍 x 整整齐齐 x 情头自由 x 无限创意
# 文章摘要：简单来说，先垫图你喜欢的图片...
# 完整提示词：需要登录后打开文章
```

**获取 Article 的方法**：
1. 登录 X 账号后用浏览器打开文章链接
2. 或者从推文正文中提取"佐料"部分（用户补充的要求）
3. 完整"汤底"（提示词模板）在文章中，需要登录

**⚠️ 浏览器风控警告**：
批量用浏览器访问 X 页面会被识别为机器人（stealth_warning），导致：
- 页面加载超时
- 被要求登录
- CAPTCHA 验证

**应对策略**：
- 每次请求间隔 3-5 秒
- 不要连续访问 10+ 个页面
- 如果出现 stealth_warning，停止浏览器操作
- 改用 xreach CLI（不受浏览器风控影响）
- 大批量提取分多批次，每批 5-10 个，间隔 30 分钟

---

## 路径 E：Article 类型推文图片下载（完整工作流）

Article 类型的推文（引用 `x.com/i/article/xxx` 的帖子），其图片不在推文的 `media` 数组里，而是在 Article 页面中。xreach 返回 `media: []`，直接用 media URL 下载会得到 0 字节。

**第一步**：r.jina.ai 解析 Article URL，提取所有图片 URL：
```bash
curl -s "https://r.jina.ai/https://x.com/xiaoxiaodong01/status/{tweet_id}" \
  -H "Accept: text/markdown"
```
返回的 markdown 中包含所有 Article 图片的原始 pbs.twimg.com URL。

用正则提取：
```python
import re
img_pattern = re.compile(r'https://pbs\.twimg\.com/media/[A-Za-z0-9_-]+\?(?:format=[^&\s]+&)?name=[^\s\)]+')
urls = img_pattern.findall(content)
unique_urls = list(dict.fromkeys(urls))  # 去重保持顺序
```

**第二步**：用 Twitter Bearer Token 绕过 403 下载：
```bash
BEARER="AAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6IWNxG7cCWhrP8K8LWul9J2p1QVaQzuH6dNjjsKIwgLexILyG3uK0uV9TPf6p1HLoquG3E2JAw9iAvPygoJ9vXK1ul8PH3Qxm0qyJgDZ"

curl -sL -o "{tweet_id}_{i}.jpg" \
  -H "Authorization: Bearer ${BEARER}" \
  "https://pbs.twimg.com/media/XXXXX?format=jpg&name=small"
```

⚠️ **关键细节**：
- URL 中的 `?format=jpg&name=small` 等参数**必须保留**，去掉会 403
- Bearer Token 是 Twitter 公开的 Guest Token，不需要认证即可使用
- 图片命名推荐 `{tweet_id}_{序号}.jpg`，可回溯到原推文

**第三步**：拼入 Markdown：
在文章中 X 链接位置插入图片画廊：
```html
<!-- image gallery for {tweet_id} -->
<div align=center>
<img src="images/{tweet_id}_1.jpg" width="300" />
<img src="images/{tweet_id}_2.jpg" width="300" />
...
</div>
```

**实测数据（2026-05-09）**：
- 12 条 Article 推文 → 88 张图片
- r.jina.ai 全部解析成功
- Bearer Token 下载全部成功（0 失败）

---

## 辅助脚本

`scripts/process_video.sh` — 自动化视频下载+转录流程（供参考，主要逻辑由 skill 在线执行）。
