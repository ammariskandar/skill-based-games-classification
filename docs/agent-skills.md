# Agent Skills — Vendored Skill Registry

This repository ships two **on-demand** agent skills under `.agents/skills/`.
They are project-local and version-controlled, so any collaborator gets them
automatically. Zed discovers skills in `.agents/skills/<name>/SKILL.md`
automatically; the bodies are **not** copied into always-loaded context.

This file records provenance and maintenance instructions only. It
intentionally does **not** duplicate the skill bodies.

## Skills

| Skill | Path | Purpose |
|-------|------|---------|
| `token-efficiency` | `.agents/skills/token-efficiency/SKILL.md` | Reduce token/tool-output waste during search, file reads, Git inspection, and command output. |
| `unslop` | `.agents/skills/unslop/SKILL.md` | Remove AI-writing patterns from human-facing prose (docs, Jira/PR summaries, handovers, README, Admin/user copy). |

## Routing (when to load each)

- **`token-efficiency`** — for large tool/file-reading operations, search,
  Git summary-first inspection, and command-output filtering.
- **`unslop`** — for substantial human-facing prose/documentation, when
  producing or substantially editing copy that should read as human.

Neither skill is unconditionally loaded. `unslop` is explicitly **not**
applied to source code, mathematical formulas, test fixtures, JSON/YAML
machine contracts, migrations, exact command output, quotations, or canonical
statistical constants.

## Provenance

### token-efficiency

- Upstream: <https://github.com/undefdev/token-efficiency>
- Pinned commit: `fdbff4e1fd4a2a70ea505a20f82da7bd73653b35`
- License: MIT (Copyright (c) 2026 Tarek Sabet)
- Imported paths:
  - `.agents/skills/token-efficiency/SKILL.md` (from `skills/token-efficiency/SKILL.md`)
  - `.agents/skills/token-efficiency/LICENSE` (from `LICENSE`)
- Modified locally: **No** (byte-identical to upstream).

### unslop

- Upstream: <https://github.com/theclaymethod/unslop>
- Pinned commit: `d81f5196167ded24f46fced04958c0c12d681798`
- License: MIT (declared in `SKILL.md` frontmatter and upstream `README.md`;
  author `claytonkim`, skill version `2.3.0`). No separate upstream LICENSE
  file exists.
- Imported paths:
  - `.agents/skills/unslop/SKILL.md`
  - `.agents/skills/unslop/references/` (core contract, command flows, taboo
    phrases, fact-preservation, rewrite examples, rubric, packs, and voice
    references)
  - `.agents/skills/unslop/presets/` (crisp, warm, expert, story)
  - `.agents/skills/unslop/scripts/` (Python helper scripts; 5 retain their
    executable bit)
- Modified locally: **No** (byte-identical to upstream).

### Intentionally omitted

- `.git/`, upstream GitHub Actions, issue/PR templates, and `.gitignore`.
- Upstream `evals/` (benchmark/eval infrastructure), `plans/`, `assets/`,
  `docs/`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`,
  `ruff.toml`, and upstream package/plugin install machinery.
- Note: `unslop/references/core-contract.md` references
  `evals/run_structure_climb.py` for the rare "remaining structure damage"
  multi-agent climb, and the maintenance/contribute references point into
  `evals/`. These are the upstream skill's own eval/maintenance machinery, not
  normal de-slop operation, and are therefore not vendored. The primary
  rewrite-validation scripts referenced by the core contract
  (`scripts/validate_preservation.py`, `scripts/banned_phrase_scan.py`,
  `scripts/structure_scan.py`, `scripts/silhouette_scan.py`,
  `scripts/readability_metrics.py`, `scripts/diff_check.py`) are all present.

## Security / supply-chain note

- All imported Python scripts were inspected before commit.
- No credential harvesting, no secrets, and no executable binary blobs.
- Normal rewrite/cleanup scripts are pure text-processing with **no network
  access**.
- `scripts/wiki_sync.py` does make an outbound call to
  `https://en.wikipedia.org/w/api.php`, but only when explicitly invoked for
  the maintenance "sync with Wikipedia" task — it is **not** part of normal
  de-slop operation and is not auto-enabled.
- `scripts/contribute.py` and `scripts/refresh_status.py` invoke `git` /
  scanner subprocesses as part of the explicit maintenance/contribution flows.
- No upstream automatic mutation or internet-sync behavior is enabled.

## How to update

1. Re-clone (or `git fetch`) the upstream repository.
2. Record the new `git rev-parse HEAD` SHA.
3. Re-copy the specific paths listed above into `.agents/skills/<name>/`,
   preserving executable bits (`cp -p` / `cp -a`).
4. Diff against the vendored copy and review before replacing.
5. Update this file's pinned commit SHA.

Do **not** run an upstream maintenance/sync command (e.g. `wiki_sync.py`)
merely because it exists. Updating is a deliberate, reviewed action.
