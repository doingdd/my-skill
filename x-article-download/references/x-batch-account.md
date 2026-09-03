<!-- x-article-download 路径 D：整账号批量下载。自 SKILL.md 拆出，步骤编号与主文件衔接。 -->

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
