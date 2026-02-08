#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add or update a weekly article in `articles.json` and sync inline JSON in `index.html`.

Inputs:
  - A source markdown file under `source/` named `WeekXX丨标题.md`.

Side effects:
  - Generates WebP versions for any local `./assets/*.png|jpg|jpeg` images referenced
    by the source (cover + markdown image links in content).
  - Updates `articles.json` (upsert by week, sort by week, set completed = count).
  - Updates inline JSON inside `index.html` <script id="articles-data" ...>.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLES_JSON = ROOT / "articles.json"
INDEX_HTML = ROOT / "index.html"


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        die(f"Command not found: {cmd[0]} (did you run `brew install webp`?)")
    except subprocess.CalledProcessError as e:
        die(f"Command failed ({e.returncode}): {' '.join(cmd)}")


def parse_week_filename(path: Path) -> tuple[int, str]:
    m = re.match(r"^Week(\d{2})丨(.+)\.md$", path.name)
    if not m:
        die(f"Unexpected source filename: {path.name} (expected WeekXX丨标题.md)")
    return int(m.group(1)), m.group(2)


def first_cover_src(lines: list[str]) -> str | None:
    for line in lines:
        s = line.strip()
        m = re.match(r"^!\[[^\]]*\]\(([^)]+)\)$", s)
        if m:
            return m.group(1).strip()
        m = re.match(r"^!\[\[(.+?)\]\]$", s)
        if m:
            # Obsidian-style embed, assume it lives under assets/
            return f"./assets/{m.group(1).strip()}"
    return None


def parse_question(lines: list[str]) -> str:
    q: list[str] = []
    in_q = False
    for line in lines:
        if line.lstrip().startswith(">"):
            in_q = True
            q.append(line.lstrip()[1:].lstrip())
        elif in_q:
            break
    question = "\n".join([x for x in q if x]).strip()
    if not question:
        die("Cannot find question blockquote (expected lines starting with '>')")
    return question


def parse_content(lines: list[str]) -> str:
    divider_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "---":
            divider_idx = i
            break
    if divider_idx is None:
        die("Cannot find content divider '---' in source markdown")
    content = "\n".join(lines[divider_idx + 1 :]).strip("\n")
    if not content.strip():
        die("Content is empty after divider '---'")
    return content


def resolve_local_path(path_str: str) -> Path | None:
    if path_str.startswith("./"):
        return ROOT / path_str[2:]
    return None


def ensure_webp(src: Path, quality: int) -> Path:
    out = src.with_suffix(".webp")
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "cwebp",
            "-q",
            str(quality),
            "-m",
            "6",
            "-mt",
            "-metadata",
            "none",
            str(src),
            "-o",
            str(out),
        ]
    )
    return out


def pick_cover_asset(week: int, title: str) -> Path:
    stem = f"Week{week:02d}丨{title}"
    for ext in (".webp", ".png", ".jpg", ".jpeg"):
        p = ROOT / "assets" / f"{stem}{ext}"
        if p.exists():
            return p
    die(f"Cannot find cover image in assets/ for {stem} (tried webp/png/jpg/jpeg)")
    raise AssertionError  # unreachable


def convert_and_rewrite_assets_in_content(content: str, quality: int) -> str:
    # Replace ./assets/*.png|jpg|jpeg with .webp if local file exists and conversion succeeds.
    pattern = re.compile(r"(\./assets/[^\s\)\"']+)\.(png|jpe?g)", re.IGNORECASE)

    def repl(match: re.Match[str]) -> str:
        base = match.group(1)
        ext = match.group(2)
        src_path = resolve_local_path(f"{base}.{ext}")
        if not src_path or not src_path.exists():
            return match.group(0)
        webp_path = ensure_webp(src_path, quality=quality)
        # Return path string with .webp suffix (keep leading ./)
        rel = webp_path.relative_to(ROOT).as_posix()
        return f"./{rel}"

    return pattern.sub(repl, content)


def upsert_article(data: dict, article: dict) -> None:
    articles = list(data.get("articles", []))
    week = article.get("week")
    replaced = False
    for i, a in enumerate(articles):
        if a.get("week") == week:
            articles[i] = article
            replaced = True
            break
    if not replaced:
        articles.append(article)
    articles.sort(key=lambda a: a.get("week", 0))
    data["articles"] = articles
    data["completed"] = len(articles)


def sync_inline_json(index_html: Path, data: dict) -> None:
    html = index_html.read_text(encoding="utf-8")
    marker = '<script id="articles-data" type="application/json">'
    start = html.find(marker)
    if start == -1:
        die('Cannot find <script id="articles-data" ...> in index.html')
    start += len(marker)
    end = html.find("</script>", start)
    if end == -1:
        die("Cannot find closing </script> for articles-data in index.html")

    inline = json.dumps(data, ensure_ascii=False, separators=(",", ": "))
    # Prevent accidental script-tag termination inside JSON string values.
    inline = inline.replace("</script>", "<\\/script>")

    index_html.write_text(html[:start] + inline + html[end:], encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Add/update a weekly article and sync site data.")
    parser.add_argument("source_md", help="Path to source markdown, e.g. source/Week39丨暂停.md")
    parser.add_argument("--quality", type=int, default=82, help="WebP quality (default: 82)")
    args = parser.parse_args()

    src = (ROOT / args.source_md).resolve() if not Path(args.source_md).is_absolute() else Path(args.source_md)
    if not src.exists():
        die(f"Source markdown not found: {src}")

    week, title = parse_week_filename(src)
    md = src.read_text(encoding="utf-8").strip("\n")
    lines = md.splitlines()

    cover_src = first_cover_src(lines)
    question = parse_question(lines)
    content = parse_content(lines)

    # Resolve cover image path
    cover_path: Path | None = None
    if cover_src:
        p = resolve_local_path(cover_src)
        if p and p.exists():
            cover_path = p
    if cover_path is None:
        cover_path = pick_cover_asset(week, title)

    # Ensure cover is webp
    cover_webp = cover_path if cover_path.suffix.lower() == ".webp" else ensure_webp(cover_path, quality=args.quality)
    cover_rel = cover_webp.relative_to(ROOT).as_posix()
    cover_ref = f"./{cover_rel}"

    # Convert any in-content assets links to webp and rewrite paths
    content = convert_and_rewrite_assets_in_content(content, quality=args.quality)

    # Load + update articles.json
    data = json.loads(ARTICLES_JSON.read_text(encoding="utf-8"))
    article = {
        "week": week,
        "title": title,
        "question": question,
        "content": content,
        "image": cover_ref,
    }
    upsert_article(data, article)

    ARTICLES_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sync_inline_json(INDEX_HTML, data)

    print(f"Updated week {week:02d} ({title})")
    print(f"- cover: {cover_ref}")
    print(f"- completed: {data.get('completed')} / {data.get('total')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

