#!/usr/bin/env python3
"""Markdown → HTML 报告（暗色模式、侧栏导航、基础表格/代码块）。

纯 stdlib，零依赖。用法：
  python3 tools/report_html.py reports/foo.md -o reports/foo.html
  python3 tools/report_html.py reports/foo.md --stdout
"""

from __future__ import annotations

import argparse
import html
import os
import re
from typing import List, Tuple

_DARK_CSS = """
:root { --bg:#0d1117; --fg:#e6edf3; --muted:#8b949e; --accent:#58a6ff;
        --border:#30363d; --code-bg:#161b22; }
* { box-sizing: border-box; }
body { margin:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background:var(--bg); color:var(--fg); line-height:1.6; }
.layout { display:flex; min-height:100vh; }
nav { width:240px; padding:1.5rem 1rem; border-right:1px solid var(--border);
      position:sticky; top:0; height:100vh; overflow-y:auto; }
nav h2 { font-size:0.85rem; color:var(--muted); text-transform:uppercase; margin:0 0 0.75rem; }
nav a { display:block; color:var(--accent); text-decoration:none; font-size:0.9rem;
        padding:0.25rem 0; }
nav a:hover { text-decoration:underline; }
main { flex:1; padding:2rem 3rem; max-width:900px; }
h1,h2,h3 { scroll-margin-top:1rem; }
h1 { border-bottom:1px solid var(--border); padding-bottom:0.5rem; }
h2 { margin-top:2rem; color:var(--accent); }
table { border-collapse:collapse; width:100%; margin:1rem 0; font-size:0.92rem; }
th,td { border:1px solid var(--border); padding:0.5rem 0.75rem; text-align:left; }
th { background:var(--code-bg); }
tr:nth-child(even) { background:rgba(255,255,255,0.02); }
code, pre { background:var(--code-bg); border-radius:4px; }
pre { padding:1rem; overflow-x:auto; }
blockquote { border-left:3px solid var(--accent); margin:1rem 0; padding-left:1rem; color:var(--muted); }
.footer { margin-top:3rem; font-size:0.8rem; color:var(--muted); }
"""


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff\- ]+", "", text.strip().lower())
    return re.sub(r"\s+", "-", s)[:60] or "section"


def _inline_md(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def parse_markdown(md: str) -> Tuple[str, List[Tuple[str, str]]]:
    """返回 (body_html, nav_items[(id, title)])。"""
    lines = md.replace("\r\n", "\n").split("\n")
    nav: List[Tuple[str, str]] = []
    out: List[str] = []
    i = 0
    in_code = False
    code_buf: List[str] = []
    table_buf: List[str] = []

    def flush_table():
        nonlocal table_buf
        if not table_buf:
            return
        rows = [r for r in table_buf if r.strip()]
        table_buf = []
        if len(rows) < 2:
            for r in rows:
                out.append(f"<p>{_inline_md(r)}</p>")
            return
        header = [c.strip() for c in rows[0].strip("|").split("|")]
        body_rows = rows[2:] if re.match(r"^[\|\s\-:]+$", rows[1]) else rows[1:]
        out.append("<table><thead><tr>")
        for h in header:
            out.append(f"<th>{_inline_md(h)}</th>")
        out.append("</tr></thead><tbody>")
        for row in body_rows:
            cells = [c.strip() for c in row.strip("|").split("|")]
            out.append("<tr>")
            for c in cells:
                out.append(f"<td>{_inline_md(c)}</td>")
            out.append("</tr>")
        out.append("</tbody></table>")

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            if in_code:
                out.append(f"<pre><code>{html.escape(chr(10).join(code_buf))}</code></pre>")
                code_buf = []
                in_code = False
            else:
                flush_table()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue
        if "|" in line and line.strip().startswith("|"):
            table_buf.append(line)
            i += 1
            continue
        flush_table()
        if line.startswith("# "):
            title = line[2:].strip()
            sid = _slug(title)
            nav.append((sid, title))
            out.append(f'<h1 id="{sid}">{_inline_md(title)}</h1>')
        elif line.startswith("## "):
            title = line[3:].strip()
            sid = _slug(title)
            nav.append((sid, title))
            out.append(f'<h2 id="{sid}">{_inline_md(title)}</h2>')
        elif line.startswith("### "):
            title = line[4:].strip()
            sid = _slug(title)
            nav.append((sid, title))
            out.append(f'<h3 id="{sid}">{_inline_md(title)}</h3>')
        elif line.startswith("> "):
            out.append(f"<blockquote><p>{_inline_md(line[2:])}</p></blockquote>")
        elif line.strip() == "":
            pass
        elif line.strip() in ("---", "***"):
            out.append("<hr>")
        else:
            out.append(f"<p>{_inline_md(line)}</p>")
        i += 1
    flush_table()
    if in_code and code_buf:
        out.append(f"<pre><code>{html.escape(chr(10).join(code_buf))}</code></pre>")
    return "\n".join(out), nav


def render_html(md: str, *, title: str = "Berkshire Report") -> str:
    body, nav = parse_markdown(md)
    nav_html = "".join(f'<a href="#{sid}">{html.escape(t)}</a>' for sid, t in nav)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)}</title>
<style>{_DARK_CSS}</style>
</head>
<body>
<div class="layout">
<nav><h2>目录</h2>{nav_html or '<span style="color:var(--muted)">无标题</span>'}</nav>
<main>{body}
<p class="footer">Generated by berkshire-ai report_html</p>
</main>
</div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Markdown → HTML（暗色模式）")
    parser.add_argument("input", help="输入 .md 文件")
    parser.add_argument("-o", "--output", help="输出 .html 路径")
    parser.add_argument("--stdout", action="store_true", help="输出到 stdout")
    parser.add_argument("--title", help="HTML 标题")
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as fh:
        md = fh.read()
    title = args.title or os.path.splitext(os.path.basename(args.input))[0]
    html_doc = render_html(md, title=title)
    if args.stdout:
        print(html_doc)
    elif args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(html_doc)
        print(f"Wrote {args.output}")
    else:
        out = os.path.splitext(args.input)[0] + ".html"
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(html_doc)
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
