#!/usr/bin/env python3
"""Install a Claude Code skill package from a git repo (stdlib only).

Two shapes exist in the wild:
  1. A real plugin marketplace (has .claude-plugin/marketplace.json at repo
     root) -- delegate to `claude plugin marketplace add <repo>`.
  2. A loose collection of skills (a skills/ dir, or SKILL.md files at repo
     root) -- clone, then for each skill dir: copy it into
     ~/.agents/skills/<name> and symlink ~/.claude/skills/<name> -> it,
     matching the layout this machine's existing skills already use.

Existing destinations are left alone (skipped), never overwritten.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AGENTS_SKILLS = Path("~/.agents/skills").expanduser()
CLAUDE_SKILLS = Path("~/.claude/skills").expanduser()


def detect_repo_type(repo_path: Path) -> str:
    if (repo_path / ".claude-plugin" / "marketplace.json").exists():
        return "marketplace"
    return "skills"


def find_skill_dirs(repo_path: Path) -> list[Path]:
    search_root = repo_path / "skills" if (repo_path / "skills").is_dir() else repo_path
    return sorted(p.parent for p in search_root.glob("*/SKILL.md"))


def install_skill(skill_dir: Path, agents_root: Path, claude_root: Path) -> dict:
    name = skill_dir.name
    real = agents_root / name
    link = claude_root / name
    if real.exists() or link.exists():
        return {"name": name, "status": "skipped", "reason": "already exists"}
    agents_root.mkdir(parents=True, exist_ok=True)
    claude_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill_dir, real)
    relative_target = os.path.relpath(real, start=claude_root)
    link.symlink_to(relative_target)
    return {"name": name, "status": "installed"}


def install_from_git(repo: str, agents_root: Path = AGENTS_SKILLS, claude_root: Path = CLAUDE_SKILLS) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "repo"
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo, str(clone_dir)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return {"error": f"git clone failed: {result.stderr.strip()}"}

        kind = detect_repo_type(clone_dir)
        if kind == "marketplace":
            result = subprocess.run(
                ["claude", "plugin", "marketplace", "add", repo],
                capture_output=True, text=True,
            )
            return {
                "mode": "marketplace",
                "ok": result.returncode == 0,
                "output": (result.stdout + result.stderr).strip(),
            }

        skill_dirs = find_skill_dirs(clone_dir)
        if not skill_dirs:
            return {"error": "no SKILL.md found (not a marketplace, no loose skills either)"}
        results = [install_skill(d, agents_root, claude_root) for d in skill_dirs]
        return {
            "mode": "skills",
            "installed": [r["name"] for r in results if r["status"] == "installed"],
            "skipped": [r["name"] for r in results if r["status"] == "skipped"],
        }


def demo():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        marketplace_repo = tmp / "mp_repo"
        (marketplace_repo / ".claude-plugin").mkdir(parents=True)
        (marketplace_repo / ".claude-plugin" / "marketplace.json").write_text("{}")
        assert detect_repo_type(marketplace_repo) == "marketplace"

        skills_repo = tmp / "skills_repo"
        (skills_repo / "skills" / "foo").mkdir(parents=True)
        (skills_repo / "skills" / "foo" / "SKILL.md").write_text("---\nname: foo\n---\nbody")
        (skills_repo / "skills" / "bar").mkdir(parents=True)
        (skills_repo / "skills" / "bar" / "SKILL.md").write_text("---\nname: bar\n---\nbody")
        assert detect_repo_type(skills_repo) == "skills"
        found = find_skill_dirs(skills_repo)
        assert {d.name for d in found} == {"foo", "bar"}

        agents_root = tmp / "agents_skills"
        claude_root = tmp / "claude_skills"
        r1 = install_skill(found[0], agents_root, claude_root)
        assert r1["status"] == "installed"
        installed_name = r1["name"]
        assert (agents_root / installed_name / "SKILL.md").exists()
        assert (claude_root / installed_name).is_symlink()
        assert (claude_root / installed_name / "SKILL.md").read_text().startswith("---")

        r2 = install_skill(found[0], agents_root, claude_root)
        assert r2["status"] == "skipped"

        # root-level (no skills/ subdir) layout also works
        flat_repo = tmp / "flat_repo"
        (flat_repo / "baz").mkdir(parents=True)
        (flat_repo / "baz" / "SKILL.md").write_text("---\nname: baz\n---\nbody")
        flat_found = find_skill_dirs(flat_repo)
        assert [d.name for d in flat_found] == ["baz"]

    print("demo: all assertions passed", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Install a Claude Code skill package from a git repo")
    parser.add_argument("repo", nargs="?", help="git URL or owner/repo of the skill package")
    parser.add_argument("--self-test", action="store_true", help="run built-in self-check and exit")
    args = parser.parse_args()

    if args.self_test:
        demo()
        return

    if not args.repo:
        parser.error("repo is required unless --self-test is given")

    print(json.dumps(install_from_git(args.repo), ensure_ascii=False))


if __name__ == "__main__":
    main()
