# OptimusClaude

**A working method for software development with Claude Code: the main session orchestrates, subagents do the work, and every change is tested, reviewed and logged before moving on.**

[Português](README.md) · [MIT License](LICENSE)

The full documentation is in Brazilian Portuguese. Linux is the tested platform.

## Install

You need Python 3.9 or newer and git. The installer checks everything else and tells you how to install what is missing.

**Option A: ask Claude.** The repository ships a root `CLAUDE.md` that teaches Claude Code how to install the kit: it
explains what will change, runs a dry run, asks before touching your `settings.json`, and helps with whatever is missing.

```bash
git clone https://github.com/fezarosa-dev/OptimusClaude.git && cd OptimusClaude && claude "instala o OptimusClaude"
```

**Option B: by hand.**

```bash
git clone https://github.com/fezarosa-dev/OptimusClaude.git
cd OptimusClaude
python3 install.py --dry-run     # shows what it would do, changes nothing
python3 install.py               # installs
```

On Windows: `powershell -ExecutionPolicy Bypass -File .\install.ps1`. WSL gives you the full session dashboard.

The installer copies `claude/` to `~/.claude` and `painel/` to `~/painel-da-sessao`, backs up every file it replaces
(`~/.claude/backups/`), never overwrites an existing `settings.json` (use `--mesclar-settings` to merge, with a diff and a
confirmation), and ends with a "Falta fazer" (to do) list. Details: [docs/instalacao.md](docs/instalacao.md).

## How it works

1. Every new request starts with the `grilling` skill: Claude asks about the open decisions, each with a recommended answer.
2. The request becomes a task `Tn` in `TASKS.md`; anything that needs your decision goes to `duvidas.md`, and the rest keeps going.
3. Urgent questions reach your phone through ntfy and can be answered in the dashboard's Questions tab.
4. The main session never writes code. Subagents do, each in its own git worktree, picking Haiku, Sonnet or Opus by difficulty.
5. Every change follows TDD: the test must fail on a real assertion before the fix, and pass after it.
6. A different subagent reviews the diff; high and medium findings are fixed, up to 3 rounds.
7. Hooks enforce the rules: no main-session code edits, no full reads of large code files, a warning when context runs low.
8. The main session commits (a `commit-msg` hook enforces the format and blocks AI attribution) and runs the local test battery, only for what the diff touches.
9. Each battery, review and fix is logged in `registros/` with date, commit and sha256; green work is merged into `dev`.
10. Nothing reaches `main` without an explicit request: a PR from `dev`, CI green, security reviews of the diff. A night mode (`scripts/noite.py`) can work through the task queue unattended, merging only into the local `dev`.

## Documentation

- [README in Portuguese](README.md): the full guide (components, a request from start to finish, night mode, token savings, security, FAQ).
- [docs/](docs/): installation, starting a project, workflow, agents and models, token savings, tests, security,
  architecture, style, languages and dependencies.
- [painel/README.md](painel/README.md): the session dashboard.
- [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md).
