#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import html as html_lib
import unicodedata
from pathlib import Path
from urllib.parse import urlparse, urlsplit

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import markdownify as md


IMG_EXT_BY_FMT = {
    'jpeg': '.jpg',
    'jpg': '.jpg',
    'png': '.png',
    'gif': '.gif',
    'webp': '.webp',
    'svg': '.svg',
}


def sanitize_filename(name: str, limit: int = 80) -> str:
    name = (name or 'wechat-article').strip()
    name = re.sub(r'[\\/:*?"<>|\n\r\t]+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip().strip('.')
    if not name:
        name = 'wechat-article'
    return name[:limit]


def slugify(name: str, limit: int = 80) -> str:
    name = sanitize_filename(name, limit)
    chars = []
    for ch in name:
        cat = unicodedata.category(ch)
        if cat.startswith(('L', 'N')):
            chars.append(ch)
        elif ch in (' ', '-', '_'):
            chars.append('-')
        else:
            chars.append('-')
    slug = ''.join(chars)
    slug = re.sub(r'-{2,}', '-', slug).strip('-_. ')
    return (slug or 'wechat-article')[:limit]


def normalize_image_url(url: str) -> str:
    if not url:
        return ''
    url = html_lib.unescape(url.strip())
    if url.startswith('//'):
        return 'https:' + url
    return url


def choose_image_src(img: Tag) -> str:
    for key in ('data-src', 'data-original', 'src'):
        val = img.get(key)
        if val and not val.startswith('data:image/svg+xml'):
            return normalize_image_url(val)
    return ''


def infer_ext(url: str, content_type: str = '') -> str:
    fmt_match = re.search(r'[?&]wx_fmt=([a-zA-Z0-9]+)', url or '')
    if fmt_match:
        return IMG_EXT_BY_FMT.get(fmt_match.group(1).lower(), '.' + fmt_match.group(1).lower())
    path = urlsplit(url or '').path
    suffix = Path(path).suffix.lower()
    if suffix and len(suffix) <= 6:
        return suffix
    if content_type:
        c = content_type.split(';', 1)[0].strip().lower()
        if '/' in c:
            ext = '.' + c.split('/', 1)[1].replace('jpeg', 'jpg')
            if len(ext) <= 6:
                return ext
    return '.jpg'


def download_image(session: requests.Session, url: str, dest: Path) -> bool:
    resp = session.get(url, timeout=60, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://mp.weixin.qq.com/'}, stream=True)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, 'wb') as f:
        for chunk in resp.iter_content(65536):
            if chunk:
                f.write(chunk)
    return True


def clean_dom(content: BeautifulSoup) -> None:
    for tag in content.find_all(['script', 'style', 'iframe']):
        tag.decompose()

    # Remove obvious wx helper attrs
    for tag in content.find_all(True):
        attrs_to_drop = []
        for attr in list(tag.attrs.keys()):
            if attr.startswith('data-') and attr not in ('data-src', 'data-original'):
                attrs_to_drop.append(attr)
            elif attr in ('class', 'id', 'style', '_width', 'contenteditable', 'leaf', 'textstyle', 'nodeleaf', 'type'):
                attrs_to_drop.append(attr)
        for attr in attrs_to_drop:
            tag.attrs.pop(attr, None)

    # Convert sections to paragraphs/divs for cleaner markdown output
    for sec in content.find_all('section'):
        has_img = bool(sec.find('img'))
        if has_img and not sec.get_text(strip=True):
            sec.name = 'div'
        else:
            sec.name = 'p'

    for span in content.find_all('span'):
        if not span.attrs:
            span.unwrap()


class WechatArticleSaver:
    def __init__(self, payload: dict, output_dir: Path):
        self.payload = payload
        self.output_dir = output_dir
        self.title = payload.get('title') or 'wechat-article'
        self.safe_title = sanitize_filename(self.title)
        self.slug = slugify(self.title)
        self.article_dir = self.output_dir / self.slug
        self.images_dir = self.article_dir / 'images'
        self.md_path = self.article_dir / f'{self.safe_title}.md'
        self.html_path = self.article_dir / f'{self.safe_title}.html'
        self.source_json_path = self.article_dir / 'source.json'
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

    def parse_content(self):
        html = self.payload.get('html') or ''
        if not html.strip():
            raise ValueError('empty html content')
        soup = BeautifulSoup(f'<div id="js_content">{html}</div>', 'html.parser')
        content = soup.select_one('#js_content')
        if not content:
            raise ValueError('missing #js_content')
        clean_dom(content)
        return soup, content

    def localize_images(self, content: Tag):
        self.images_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for img in content.find_all('img'):
            src = choose_image_src(img)
            if not src:
                img.decompose()
                continue
            count += 1
            ext = infer_ext(src)
            local_name = f'{count:03d}{ext}'
            local_path = self.images_dir / local_name
            try:
                download_image(self.session, src, local_path)
                img.attrs = {'src': f'images/{local_name}', 'alt': img.get('alt', '') or ''}
            except Exception:
                # keep remote url if download failed, but still prefer usable output
                img.attrs = {'src': src, 'alt': img.get('alt', '') or ''}
        return count

    def build_html_document(self, content_html: str) -> str:
        title = html_lib.escape(self.payload.get('title') or '')
        account = html_lib.escape(self.payload.get('account') or '')
        author = html_lib.escape(self.payload.get('author') or '')
        pub = html_lib.escape(self.payload.get('publish_time') or '')
        source = html_lib.escape(self.payload.get('url') or '')
        desc = html_lib.escape(self.payload.get('description') or '')
        return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <meta name="description" content="{desc}" />
  <style>
    body {{ max-width: 780px; margin: 40px auto; padding: 0 16px; font: 16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",Arial,sans-serif; color: #222; }}
    .meta {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
    img {{ max-width: 100%; height: auto; display: block; margin: 16px auto; }}
    p {{ margin: 1em 0; }}
    blockquote {{ border-left: 4px solid #ddd; padding-left: 12px; color: #555; }}
    pre {{ overflow-x: auto; background: #f7f7f7; padding: 12px; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="meta">公众号：{account} &nbsp; 作者：{author} &nbsp; 发布时间：{pub}<br />来源：<a href="{source}">{source}</a></div>
  <article>
    {content_html}
  </article>
</body>
</html>'''

    def build_markdown(self, content_html: str) -> str:
        frontmatter = {
            'title': self.payload.get('title') or '',
            'account': self.payload.get('account') or '',
            'author': self.payload.get('author') or '',
            'publish_time': self.payload.get('publish_time') or '',
            'source_url': self.payload.get('url') or '',
            'description': self.payload.get('description') or '',
            'cover': self.payload.get('cover') or '',
        }
        yaml_lines = ['---']
        for k, v in frontmatter.items():
            v = str(v).replace('"', '\\"')
            yaml_lines.append(f'{k}: "{v}"')
        yaml_lines.append('---\n')

        markdown_body = md(content_html, heading_style='ATX', bullets='-', strip=['span'])
        markdown_body = re.sub(r'\n{3,}', '\n\n', markdown_body).strip() + '\n'
        return '\n'.join(yaml_lines) + '\n' + markdown_body

    def save(self):
        self.article_dir.mkdir(parents=True, exist_ok=True)
        self.source_json_path.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding='utf-8')

        _, content = self.parse_content()
        image_count = self.localize_images(content)
        content_html = ''.join(str(child) for child in content.children)
        html_doc = self.build_html_document(content_html)
        self.html_path.write_text(html_doc, encoding='utf-8')

        md_ok = False
        error = None
        try:
            markdown = self.build_markdown(content_html)
            self.md_path.write_text(markdown, encoding='utf-8')
            md_ok = True
        except Exception as exc:
            error = str(exc)

        return {
            'title': self.title,
            'article_dir': str(self.article_dir),
            'markdown_path': str(self.md_path) if md_ok else None,
            'html_path': str(self.html_path),
            'images_dir': str(self.images_dir),
            'image_count': image_count,
            'source_json_path': str(self.source_json_path),
            'markdown_ok': md_ok,
            'error': error,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding='utf-8'))
    saver = WechatArticleSaver(payload, Path(args.output_dir))
    result = saver.save()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False))
        sys.exit(1)
