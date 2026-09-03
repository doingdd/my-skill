<!-- x-article-download 路径 E：Article 类型推文图片下载。自 SKILL.md 拆出。 -->

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
