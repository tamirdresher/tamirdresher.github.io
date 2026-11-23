"""Maintain committed tag archives for GitHub Pages' safe, legacy Jekyll build."""

import argparse
import json
from pathlib import Path
import re
from urllib.parse import quote_plus

import yaml


ROOT = Path(__file__).resolve().parents[1]


def parse_page(text):
    text = text.replace("\r\n", "\n")
    match = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", text, re.DOTALL)
    if not match:
        return {}, text
    return yaml.safe_load(match[1]) or {}, text[match.end():]


def read_page(path):
    return parse_page(path.read_text(encoding="utf-8-sig"))


def frontmatter(path):
    return read_page(path)[0]


def tag_slug(tag):
    return tag.replace(" ", "-").lower()


def archive_pages(root):
    groups = {}
    for path in sorted((root / "_posts").rglob("*")):
        if path.suffix.lower() not in (".md", ".markdown", ".html"):
            continue
        data = frontmatter(path)
        if data.get("published") is False:
            continue
        tags = data.get("tags") or []
        if isinstance(tags, str):
            tags = tags.split()
        for tag in tags:
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError(f"Invalid tag in {path}")
            slug = quote_plus(tag_slug(tag), safe="")
            groups.setdefault(slug, set()).add(tag)

    pages = {}
    for slug, keys in sorted(groups.items()):
        path = root / "tags" / f"{slug}.md"
        data, body = read_page(path) if path.exists() else ({}, "")
        tags = sorted(keys)
        # Preserve editorial metadata on existing, hand-authored archives.
        data.setdefault("layout", "tag")
        data.setdefault("title", tags[0])
        data["tag"] = tags[0]
        data["permalink"] = f"/tags/{slug}/"
        if not path.exists() or data.get("generated_tag_archive"):
            data["generated_tag_archive"] = True
        if len(tags) > 1:
            data["tag_keys"] = tags
        else:
            data.pop("tag_keys", None)
        pages[path] = "---\n" + "".join(
            f"{key}: {json.dumps(value, ensure_ascii=False)}\n"
            for key, value in data.items()
        ) + "---\n" + body
    return pages


def generate(root=ROOT, check=False):
    pages = archive_pages(root)
    stale = [
        path for path in (root / "tags").glob("*.md")
        if path not in pages and frontmatter(path).get("generated_tag_archive")
    ]
    changed = [
        path for path, content in pages.items()
        if not path.exists() or path.read_text(encoding="utf-8") != content
    ]
    if check:
        if changed or stale:
            raise ValueError("Tag archives need regeneration: " + ", ".join(
                str(path.relative_to(root)) for path in changed + stale
            ))
    else:
        (root / "tags").mkdir(exist_ok=True)
        for path in changed:
            path.write_text(pages[path], encoding="utf-8", newline="\n")
        for path in stale:
            path.unlink()
    return len(pages)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(f"{generate(check=args.check)} tag archives {'checked' if args.check else 'generated'}")
