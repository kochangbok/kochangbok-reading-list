#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import shutil
from datetime import datetime
from pathlib import Path

SRC = Path('substack_markdown_ko')
OUT = Path('public')
ARTICLE_OUT = OUT / 'articles'
SKIP = {'README.md', 'TRANSLATION_GUIDE.md'}

STYLE = r'''
:root{color-scheme:light;--fg:#1f1b18;--muted:#766d65;--line:#e8ded4;--paper:#fffaf4;--bg:#f3eee8;--accent:#8a4b2a}*{box-sizing:border-box}html{overflow-x:hidden;-webkit-text-size-adjust:100%}body{margin:0;overflow-x:hidden;background:var(--bg);color:var(--fg);font-family:ui-serif,Georgia,'Times New Roman','Noto Serif KR',serif;line-height:1.78;word-break:keep-all}a{color:var(--accent);text-underline-offset:.18em;overflow-wrap:anywhere}header.site{padding:48px 20px 24px;text-align:center}header.site h1{margin:0;font-size:clamp(2rem,5vw,4rem);letter-spacing:-.04em}header.site p{margin:10px auto 0;max-width:720px;color:var(--muted)}main{width:min(100%,920px);margin:0 auto;padding:20px}.card,.article{background:var(--paper);border:1px solid var(--line);border-radius:24px;box-shadow:0 20px 60px #5b432414}.list{display:grid;gap:14px;padding:0;margin:28px 0;list-style:none}.list a{display:block;min-height:56px;padding:22px 24px;text-decoration:none}.list strong{display:block;font-size:1.2rem;letter-spacing:-.03em;color:var(--fg);overflow-wrap:anywhere}.meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:6px;color:var(--muted);font-size:.92rem}.article{padding:clamp(24px,5vw,64px)}.article header{border-bottom:1px solid var(--line);margin-bottom:34px;padding-bottom:24px}.article h1{font-size:clamp(2rem,5vw,3.6rem);line-height:1.12;letter-spacing:-.05em;margin:0 0 12px;overflow-wrap:anywhere}.subtitle{font-size:1.15rem;color:var(--muted);margin:0}.article h2{font-size:1.8rem;line-height:1.25;margin:2.4em 0 .7em;letter-spacing:-.04em;overflow-wrap:anywhere}.article h3{font-size:1.35rem;margin:2em 0 .5em;overflow-wrap:anywhere}.article p,.article li{font-size:1.08rem}.article p{margin:1.15em 0}.article blockquote{margin:2em 0;padding:8px 0 8px 22px;border-left:4px solid var(--accent);color:#4d4038;background:#fff3e7}.article img{display:block;max-width:100%;height:auto;border-radius:16px;margin:26px auto}.article hr{border:0;border-top:1px solid var(--line);margin:40px 0}.article pre{max-width:100%;white-space:pre-wrap;background:#211c18;color:#fff7ee;padding:18px;border-radius:14px;overflow:auto}.article code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}.top{display:inline-block;min-height:44px;margin-bottom:18px;font-family:ui-sans-serif,system-ui,sans-serif;font-size:.9rem}.footer{padding:30px 20px 60px;text-align:center;color:var(--muted);font-family:ui-sans-serif,system-ui,sans-serif;font-size:.9rem}@media(max-width:640px){header.site{padding:34px 14px 14px}main{padding:0}.list{gap:10px;margin:18px 10px}.list a{padding:18px}.article{border-left:0;border-right:0;border-radius:0;box-shadow:none;padding:22px 18px}.article header{margin-bottom:24px}.article h1{font-size:clamp(1.8rem,10vw,2.5rem)}.article h2{font-size:1.45rem}.article p,.article li{font-size:1rem}.article blockquote{margin-left:-18px;margin-right:-18px;padding:10px 18px}.article img{border-radius:10px}.footer{padding-bottom:calc(36px + env(safe-area-inset-bottom))}}
'''

def parse_frontmatter(text: str):
    if not text.startswith('---\n'):
        return {}, text
    end = text.find('\n---\n', 4)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        v = v.strip().strip('"')
        meta[k.strip()] = v
    return meta, text[end + 5:].strip()

def inline(s: str) -> str:
    placeholders = []
    def keep(m):
        placeholders.append(m.group(0))
        return f'\0{len(placeholders)-1}\0'
    s = re.sub(r'<a\b[^>]*>.*?</a>|<img\b[^>]*>', keep, s)
    s = html.escape(s, quote=False)
    s = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', lambda m: f'<img src="{html.escape(m.group(2), quote=True)}" alt="{html.escape(m.group(1), quote=True)}" loading="lazy">', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', s)
    for i, raw in enumerate(placeholders):
        s = s.replace(f'\0{i}\0', raw)
    return s

def md_to_html(md: str) -> str:
    lines = md.splitlines()
    out, para, list_buf, quote = [], [], [], []
    in_code = False
    code = []
    def flush_para():
        if para:
            out.append('<p>' + inline(' '.join(x.strip() for x in para)) + '</p>')
            para.clear()
    def flush_list():
        if list_buf:
            out.append('<ul>' + ''.join(f'<li>{inline(x)}</li>' for x in list_buf) + '</ul>')
            list_buf.clear()
    def flush_quote():
        if quote:
            out.append('<blockquote>' + ''.join(f'<p>{inline(x)}</p>' for x in quote if x.strip()) + '</blockquote>')
            quote.clear()
    for raw in lines:
        line = raw.rstrip()
        if line.strip().startswith('```'):
            flush_para(); flush_list(); flush_quote()
            if in_code:
                out.append('<pre><code>' + html.escape('\n'.join(code)) + '</code></pre>')
                code.clear(); in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code.append(line); continue
        stripped = line.strip()
        if not stripped:
            flush_para(); flush_list(); flush_quote(); continue
        if stripped == '[' or stripped == ']':
            continue
        if re.fullmatch(r'[-*_]{3,}', stripped):
            flush_para(); flush_list(); flush_quote(); out.append('<hr>'); continue
        m = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if m:
            flush_para(); flush_list(); flush_quote(); level = min(len(m.group(1)), 3)
            out.append(f'<h{level}>{inline(m.group(2))}</h{level}>'); continue
        m = re.match(r'^[-*]\s+(.+)$', stripped)
        if m:
            flush_para(); flush_quote(); list_buf.append(m.group(1)); continue
        if stripped.startswith('>'):
            flush_para(); flush_list(); quote.append(stripped.lstrip('> ').strip()); continue
        if re.match(r'^!\[', stripped):
            flush_para(); flush_list(); flush_quote(); out.append(inline(stripped)); continue
        para.append(stripped)
    flush_para(); flush_list(); flush_quote()
    return '\n'.join(out)

def slug(path: Path) -> str:
    return path.stem

def nice_date(s: str) -> str:
    if not s: return ''
    try: return datetime.fromisoformat(s.replace('Z','+00:00')).date().isoformat()
    except Exception: return s[:10]

def page(title, body, desc=''):
    return '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>' + html.escape(title) + '</title><meta name="description" content="' + html.escape(desc or title, quote=True) + '"><style>' + STYLE + '</style></head><body>' + body + '</body></html>\n'

def main():
    if OUT.exists(): shutil.rmtree(OUT)
    ARTICLE_OUT.mkdir(parents=True)
    articles = []
    for src in sorted(p for p in SRC.glob('*.md') if p.name not in SKIP):
        meta, body_md = parse_frontmatter(src.read_text(encoding='utf-8'))
        title = meta.get('title') or src.stem
        subtitle = meta.get('subtitle') or ''
        date = nice_date(meta.get('date_published',''))
        body = '<main><article class="article"><a class="top" href="/">← 목록으로</a><header><h1>' + html.escape(title) + '</h1>'
        if subtitle: body += '<p class="subtitle">' + html.escape(subtitle) + '</p>'
        body += '<div class="meta"><span>' + html.escape(date) + '</span><span>' + html.escape(meta.get('author','')) + '</span></div></header>' + md_to_html(body_md) + '</article></main><p class="footer">읽기용 한국어 HTML 아카이브</p>'
        name = slug(src) + '.html'
        (ARTICLE_OUT / name).write_text(page(title, body, subtitle), encoding='utf-8')
        articles.append({**meta, 'title': title, 'subtitle': subtitle, 'date': date, 'href': '/articles/' + name})
    items = ''.join('<li class="card"><a href="{href}"><strong>{title}</strong><span class="meta"><span>{date}</span><span>{subtitle}</span></span></a></li>'.format(href=a['href'], title=html.escape(a['title']), date=html.escape(a['date']), subtitle=html.escape(a['subtitle'])) for a in articles)
    home = '<header class="site"><h1>고창복 읽기 목록</h1><p>한국어 번역 글을 긴 호흡으로 읽기 좋게 정리한 HTML 아카이브입니다.</p></header><main><ul class="list">' + items + '</ul></main><p class="footer">총 ' + str(len(articles)) + '편</p>'
    (OUT / 'index.html').write_text(page('고창복 읽기 목록', home, '한국어 글 HTML 읽기 목록'), encoding='utf-8')
    (OUT / '404.html').write_text(page('페이지 없음', '<main><article class="article"><h1>페이지 없음</h1><p><a href="/">목록으로 돌아가기</a></p></article></main>'), encoding='utf-8')
    (OUT / 'vercel.json').write_text('{\n  "cleanUrls": true,\n  "trailingSlash": false\n}\n', encoding='utf-8')
    print(f'built {len(articles)} articles')

if __name__ == '__main__': main()
