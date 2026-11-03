#!/usr/bin/env python3
"""Compact search over an Obsidian vault (stdlib only, no dependencies).

Reads the same source of truth Obsidian itself uses (frontmatter + inline
text in the .md files) instead of maintaining a separate index, since
Obsidian's own tag/link cache lives in an internal IndexedDB that isn't
readable from outside the app.

Covers every relation type Obsidian supports: tags (frontmatter + inline),
wikilinks (plain/heading/block, including embeds), aliases, frontmatter
property links, external links, and folder placement.
"""

import argparse
import json
import re
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
INLINE_TAG_RE = re.compile(r"(?<!\S)#([A-Za-z0-9_/-]+)")
WIKILINK_RE = re.compile(r"(!)?\[\[([^\]]+)\]\]")
EXTERNAL_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\((https?://[^)\s]+)\)")


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    data: dict = {}
    current_key = None
    for line in block.splitlines():
        if re.match(r"^\S.*:", line):
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest.startswith("[") and rest.endswith("]"):
                data[key] = [v.strip().strip('"\'') for v in rest[1:-1].split(",") if v.strip()]
                current_key = None
            elif rest:
                data[key] = rest.strip('"\'')
                current_key = None
            else:
                data[key] = []
                current_key = key
        elif line.strip().startswith("- ") and current_key:
            data[current_key].append(line.strip()[2:].strip('"\''))
    return data


def parse_wikilink(inner: str):
    """Return (target, heading, block, display) for the content inside [[ ]]."""
    display = None
    if "|" in inner:
        inner, display = inner.split("|", 1)
        display = display.strip()
    target, heading, block = inner, None, None
    if "#" in inner:
        target, frag = inner.split("#", 1)
        if frag.startswith("^"):
            block = frag[1:].strip()
        else:
            heading = frag.strip()
    return target.strip(), heading, block, display


def extract_links(body: str):
    links = []
    for is_embed, inner in WIKILINK_RE.findall(body):
        target, heading, block, display = parse_wikilink(inner)
        if not target:
            continue  # same-note heading/block self-reference, not a cross-note relation
        links.append({
            "target": target,
            "type": "embed" if is_embed else "link",
            "heading": heading,
            "block": block,
            "display": display,
        })
    return links


def extract_external_links(body: str):
    return [{"text": t, "url": u} for t, u in EXTERNAL_LINK_RE.findall(body)]


def extract_frontmatter_links(frontmatter: dict):
    result = []
    for key, value in frontmatter.items():
        values = value if isinstance(value, list) else [value]
        for v in values:
            if not isinstance(v, str):
                continue
            for is_embed, inner in WIKILINK_RE.findall(v):
                target, heading, block, display = parse_wikilink(inner)
                if target:
                    result.append({"property": key, "target": target})
    return result


def note_tags(frontmatter: dict, body: str) -> set:
    tags = set()
    fm_tags = frontmatter.get("tags", [])
    if isinstance(fm_tags, str):
        fm_tags = [fm_tags]
    tags.update(t.lstrip("#") for t in fm_tags if t)
    tags.update(INLINE_TAG_RE.findall(body))
    return tags


def note_aliases(frontmatter: dict) -> list:
    aliases = frontmatter.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    return [a for a in aliases if a]


class Vault:
    def __init__(self, root: Path):
        self.root = root
        self.notes = []  # list of dicts, one per note
        self.by_stem = {}
        self.alias_to_stem = {}
        self._load()

    def _load(self):
        for path in sorted(self.root.rglob("*.md")):
            rel = path.relative_to(self.root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            fm = parse_frontmatter(text)
            body = FRONTMATTER_RE.sub("", text, count=1)
            note = {
                "path": str(rel),
                "stem": path.stem,
                "folder": str(rel.parent) if str(rel.parent) != "." else "",
                "title": fm.get("title", path.stem),
                "tags": sorted(note_tags(fm, body)),
                "aliases": note_aliases(fm),
                "frontmatter": fm,
                "links": extract_links(body),
                "frontmatter_links": extract_frontmatter_links(fm),
                "external_links": extract_external_links(body),
                "body": body,
            }
            self.notes.append(note)
            self.by_stem[note["stem"]] = note
            for a in note["aliases"]:
                self.alias_to_stem[a] = note["stem"]

    def resolve(self, name: str):
        """Resolve a note name or alias to its stem, if it exists in the vault."""
        if name in self.by_stem:
            return name
        return self.alias_to_stem.get(name, name)

    def find(self, name: str):
        stem = self.resolve(name)
        return self.by_stem.get(stem)

    def all_targets(self, note):
        return [l["target"] for l in note["links"]] + [l["target"] for l in note["frontmatter_links"]]

    def backlinks(self, name: str):
        stem = self.resolve(name)
        result = []
        for note in self.notes:
            for target in self.all_targets(note):
                if self.resolve(target) == stem and note["stem"] != stem:
                    result.append(note["path"])
                    break
        return result


def trim(items, limit):
    if limit and len(items) > limit:
        return items[:limit] + [f"... +{len(items) - limit} more (use --limit to see more)"]
    return items


def cmd_list(v: Vault, args):
    items = [n["path"] for n in v.notes]
    return trim(items, args.limit)


def cmd_tags(v: Vault, args):
    counts: dict = {}
    for n in v.notes:
        for t in n["tags"]:
            counts[t] = counts.get(t, 0) + 1
    items = [{"tag": t, "count": c} for t, c in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]
    return trim(items, args.limit)


def cmd_by_tag(v: Vault, args):
    target = args.value.lstrip("#")
    items = [n["path"] for n in v.notes if target in n["tags"]]
    return trim(items, args.limit)


def cmd_folder(v: Vault, args):
    target = args.value.strip("/")
    items = [n["path"] for n in v.notes if n["folder"] == target]
    return trim(items, args.limit)


def cmd_search(v: Vault, args):
    query = args.value.lower()
    items = []
    for n in v.notes:
        for i, line in enumerate(n["body"].splitlines(), start=1):
            if query in line.lower():
                items.append({"note": n["path"], "line": i, "text": line.strip()[:200]})
    return trim(items, args.limit)


def cmd_links(v: Vault, args):
    n = v.find(args.value)
    if not n:
        return {"error": f"note not found: {args.value}"}
    return n["links"] + [{"target": l["target"], "type": "frontmatter", "property": l["property"]}
                          for l in n["frontmatter_links"]]


def cmd_backlinks(v: Vault, args):
    if not v.find(args.value):
        return {"error": f"note not found: {args.value}"}
    return trim(v.backlinks(args.value), args.limit)


def cmd_embeds(v: Vault, args):
    n = v.find(args.value)
    if not n:
        return {"error": f"note not found: {args.value}"}
    return [l["target"] for l in n["links"] if l["type"] == "embed"]


def cmd_alias(v: Vault, args):
    stem = v.resolve(args.value)
    n = v.by_stem.get(stem)
    if not n:
        return {"error": f"not found: {args.value}"}
    return {"note": n["path"], "aliases": n["aliases"]}

def cmd_note(v: Vault, args):
    n = v.find(args.value)
    if not n:
        return {"error": f"note not found: {args.value}"}
    return {
        "path": n["path"],
        "folder": n["folder"],
        "title": n["title"],
        "tags": n["tags"],
        "aliases": n["aliases"],
        "frontmatter": n["frontmatter"],
        "links": n["links"],
        "frontmatter_links": n["frontmatter_links"],
        "external_links": n["external_links"],
        "backlinks": v.backlinks(n["stem"]),
    }


def cmd_related(v: Vault, args):
    n = v.find(args.value)
    if not n:
        return {"error": f"note not found: {args.value}"}
    my_tags = set(n["tags"])
    outgoing = {v.resolve(t) for t in v.all_targets(n)}
    incoming = {v.resolve(t) for t in v.backlinks(n["stem"])}
    scored = []
    for other in v.notes:
        if other["stem"] == n["stem"]:
            continue
        shared_tags = my_tags & set(other["tags"])
        score = len(shared_tags) * 2
        if other["stem"] in outgoing:
            score += 3
        if other["path"] in incoming or other["stem"] in incoming:
            score += 3
        if score > 0:
            scored.append({"note": other["path"], "score": score, "shared_tags": sorted(shared_tags)})
    scored.sort(key=lambda x: -x["score"])
    limit = args.limit or 10
    return trim(scored, limit)


def cmd_orphans(v: Vault, args):
    linked = set()
    for n in v.notes:
        for t in v.all_targets(n):
            linked.add(v.resolve(t))
    items = [n["path"] for n in v.notes if n["stem"] not in linked and not n["links"] and not n["frontmatter_links"]]
    return trim(items, args.limit)


def cmd_stats(v: Vault, args):
    total_links = sum(len(n["links"]) + len(n["frontmatter_links"]) for n in v.notes)
    all_tags = set()
    for n in v.notes:
        all_tags.update(n["tags"])
    return {
        "notes": len(v.notes),
        "tags": len(all_tags),
        "links": total_links,
        "orphans": len(cmd_orphans(v, argparse.Namespace(limit=0))),
    }


def cmd_graph(v: Vault, args):
    items = [{"path": n["path"], "tags": n["tags"], "links": [t["target"] for t in n["links"]]} for n in v.notes]
    return trim(items, args.limit)


COMMANDS = {
    "list": cmd_list,
    "tags": cmd_tags,
    "by-tag": cmd_by_tag,
    "folder": cmd_folder,
    "search": cmd_search,
    "links": cmd_links,
    "backlinks": cmd_backlinks,
    "embeds": cmd_embeds,
    "alias": cmd_alias,
    "note": cmd_note,
    "related": cmd_related,
    "orphans": cmd_orphans,
    "stats": cmd_stats,
    "graph": cmd_graph,
}


def main():
    parser = argparse.ArgumentParser(description="Compact search over an Obsidian vault")
    parser.add_argument("--vault", required=True, help="Path to the vault root")
    parser.add_argument("--limit", type=int, default=50, help="Max items to return (0 = unlimited)")
    parser.add_argument("command", choices=COMMANDS.keys())
    parser.add_argument("value", nargs="?", default="", help="tag/query/note name/folder, depending on command")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser()
    if not vault.is_dir():
        print(json.dumps({"error": f"vault not found: {vault}"}))
        sys.exit(1)

    v = Vault(vault)
    result = COMMANDS[args.command](v, args)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
