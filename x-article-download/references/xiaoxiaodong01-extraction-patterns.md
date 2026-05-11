# @xiaoxiaodong01 提取模式笔记

> 实战时间：2026-05-07（第二次）
> 账号：https://x.com/xiaoxiaodong01（小小东）
> 内容：GPT-image2 提示词分享

---

## ⚠️ 重要：r.jina.ai 大规模 SSL 失败（2026-05-07 实测）

**问题**：`r.jina.ai` 批量提取 102 条推文时全部 SSL EOF 错误：
```
<urlopen error EOF occurred in violation of protocol (_ssl.c:1129)>
```
- Batch 0 (35条): 全部失败
- Batch 1 (35条): 全部失败
- Batch 2 (32条): 全部失败

**结论**：r.jina.ai 只适合单条验证，不适合批量提取。

**正确工作流（2026-05-07 实测成功）**：
1. `xreach tweets @xiaoxiaodong01 --json -n 100` → 分页拉全部推文 + media URL（可靠）
2. xreach text 含代码块（```）→ 真实提示词
3. xreach text 无代码块 → 只有描述/佐料，完整提示词在 Article 里（需登录）
4. 图片用 `media[].url` 直接下载（urllib 或 curl，8并发）

**xreach 实测数据**：
- 9 页分页 → 122 条推文
- 含提示词+图片：73 条
- 含真实代码块（提示词）：4 条
- 图片下载成功率：93/99（6条 SSL 失败可忽略）

---

## 内容结构分类

| 类型 | 特征 | 可提取性 |
|------|------|---------|
| **推文里有代码块** | 提示词直接在推文正文里，用 ``` 包裹 | ✅ xreach 完整提取 |
| **推文里有佐料片段** | "佐料：xxx" 格式，完整提示词在 Article 里 | ⚠️ xreach 只有佐料，Article 需登录 |
| **引用的 X Article** | 推文引用自己的 x.com/i/article/xxx | ⚠️ Article 需登录才能看完整内容 |
| **引用的微信公众号文章** | t.co 指向 mp.weixin.qq.com | → 走 wechat-article-md-local skill |

## 核心发现：xreach text 截断规律

- xreach 的 `text` 字段：
  - 短推文（≤280字）：完整
  - 含代码块的推文：代码块内容完整保留
  - 长推文/引用 Article：text 字段存在但不等于页面完整内容
- **关键判断**：看 `text` 里有没有 ` ``` ` 代码块。有则为真实提示词，无则说明完整内容在 Article 里（需登录）

## 已成功提取的含真实代码块推文（4条）

| # | 推文ID | 主题 |
|---|--------|------|
| 1 | 2050042358297989436 | 乐高字体 |
| 2 | 2047861856434544979 | 算命先生 |
| 3 | 2047846471123562742 | 报纸头条 |
| 4 | 2047742187853775109 | 掌纹算命 |

## 数据文件

```
<OUTPUT_DIR>/xiaoxiaodong01/
├── GPT2提示词完整合集.md   # 73条整理（4条含真实提示词）
├── tweets_xreach_all.json  # 122条原始推文（xreach全量）
└── images_by_tweet/       # 93张图片
```
