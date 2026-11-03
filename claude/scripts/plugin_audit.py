#!/usr/bin/env python3
"""Audit the always-on token cost of enabled Claude Code plugins (stdlib only).

Cross-references ~/.claude/settings.json (enabledPlugins) against
~/.claude/plugins/plugin-catalog-cache.json (per-plugin token costs) so the
always_on cost paid every single session -- regardless of whether a plugin
is ever used -- can be checked without writing a one-off script each time.
"""

import argparse
import json
import sys
from pathlib import Path

SETTINGS = Path("~/.claude/settings.json").expanduser()
CATALOG = Path("~/.claude/plugins/plugin-catalog-cache.json").expanduser()
DEFAULT_MODEL = "claude-sonnet-4-6"


def load():
    settings = json.loads(SETTINGS.read_text())
    catalog = json.loads(CATALOG.read_text())
    enabled = [k for k, v in settings.get("enabledPlugins", {}).items() if v]
    plugins = catalog["catalog"]["plugins"]
    return enabled, plugins


def cmd_list(args):
    enabled, plugins = load()
    rows = []
    for key in enabled:
        entry = plugins.get(key)
        if not entry:
            rows.append({"plugin": key, "always_on": None, "on_invoke": None, "note": "not in catalog cache"})
            continue
        tok = entry.get("tokens", {}).get(args.model, {})
        rows.append({
            "plugin": key,
            "always_on": tok.get("always_on", 0),
            "on_invoke": tok.get("on_invoke", 0),
        })
    rows.sort(key=lambda r: -(r["always_on"] or 0))
    return rows


def cmd_total(args):
    rows = cmd_list(args)
    return {
        "plugins": len(rows),
        "total_always_on": sum(r["always_on"] or 0 for r in rows),
        "total_on_invoke": sum(r["on_invoke"] or 0 for r in rows),
    }


COMMANDS = {"list": cmd_list, "total": cmd_total}


def main():
    parser = argparse.ArgumentParser(description="Audit always-on token cost of enabled Claude Code plugins")
    parser.add_argument("command", choices=COMMANDS.keys())
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model key to read token costs for")
    args = parser.parse_args()

    if not SETTINGS.exists() or not CATALOG.exists():
        print(json.dumps({"error": "settings.json or plugin-catalog-cache.json not found"}))
        sys.exit(1)

    print(json.dumps(COMMANDS[args.command](args), ensure_ascii=False))


if __name__ == "__main__":
    main()
