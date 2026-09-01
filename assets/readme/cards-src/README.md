# 展示卡生成器

`cards.json` 是 12 个 skill 中 8 张"真实产出卡"的内容（其余 4 个 skill 用真实截图）。改卡片只改这里，不要手改 PNG。

```bash
python3 build_cards.py                      # 生成每张卡的 HTML 与叠放的 index.html
python3 -m http.server 8767                 # Playwright 不接受 file:// ，用本地服务
# 用 Playwright 以 1200x675 视口对 index.html 做整页截图，再按 675px 切分到 ../cards/<name>.png
```
