# Agent Skills — Vendored Skill Registry

This repository ships **on-demand** agent skills under `.agents/skills/`. They
are project-local and version-controlled, so any collaborator gets them
automatically. Zed discovers skills in `.agents/skills/<name>/SKILL.md`
automatically; the bodies are **not** copied into always-loaded context.

This file records provenance and maintenance instructions only. It
intentionally does **not** duplicate the skill bodies.

## Installed inventory

### Core agent hygiene

| Skill | Path | Purpose |
|-------|------|---------|
| `token-efficiency` | `.agents/skills/token-efficiency/SKILL.md` | Reduce token/tool-output waste during search, file reads, Git inspection, and command output. |
| `unslop` | `.agents/skills/unslop/SKILL.md` | Remove AI-writing patterns from human-facing prose (docs, Jira/PR summaries, handovers, README, Admin/user copy). |

### Engineering / reasoning

| Skill | Path | Purpose |
|-------|------|---------|
| `diagnosing-bugs` | `.agents/skills/diagnosing-bugs/SKILL.md` | Diagnosis loop for hard bugs and performance regressions. |
| `code-review` | `.agents/skills/code-review/SKILL.md` | Review changes since a fixed point along Standards and Spec axes. |
| `domain-modeling` | `.agents/skills/domain-modeling/SKILL.md` | Build/sharpen the project's domain model and ADR/context records. |
| `codebase-design` | `.agents/skills/codebase-design/SKILL.md` | Deep-module design vocabulary: interfaces, seams, dependency direction. |
| `research` | `.agents/skills/research/SKILL.md` | Investigate a question against primary sources; write source-backed notes. |
| `browser-interaction-engineering` | `.agents/skills/browser-interaction-engineering/SKILL.md` | Discipline for F2/F3 frontend work that depends on real browser runtime state (scrolling, animation, gestures, geometry, timing). |

### Continuity / documentation

| Skill | Path | Purpose |
|-------|------|---------|
| `handoff` | `.agents/skills/handoff/SKILL.md` | Compact a conversation into a handoff document for another agent. |
| `writing-for-agents` | `.agents/skills/writing-for-agents/SKILL.md` | Writing skills / AGENTS.md / agent-facing docs with progressive disclosure. |
| `wizard` | `.agents/skills/wizard/SKILL.md` | Generate an interactive bash wizard for human-only manual steps. |

## Routing (when to load each)

- **`token-efficiency`** — large tool/file-reading, search, Git summary-first
  inspection, command-output filtering.
- **`unslop`** — substantial human-facing prose/documentation.
- **`diagnosing-bugs`** — reproducing defects, failing tests, unexpected
  runtime behavior, symptom-vs-cause.
- **`code-review`** — pre-merge/audit review of a branch, PR, or ticket.
- **`domain-modeling`** — introducing/changing domain concepts, models,
  statuses, terminology, ownership.
- **`codebase-design`** — substantial new modules/services, dependency
  direction, seams, interface design.
- **`research`** — external/upstream documentation or semantics are uncertain.
- **`browser-interaction-engineering`** — frontend work depending on scrolling,
  animation, gestures, runtime geometry, or timing (F2/F3 risk).
- **`handoff`** — context compaction or transferring work between agents.
- **`writing-for-agents`** — agent-facing docs, handovers, AGENTS.md guidance.
- **`wizard`** — concise manual human operational verification (Admin,
  Postman, local checks, one-off setup).

None are unconditionally loaded. `unslop` is explicitly **not** applied to
source code, mathematical formulas, test fixtures, JSON/YAML machine
contracts, migrations, exact command output, quotations, or canonical
statistical constants.

## Local overrides / precedence

Project rules always take precedence. In particular:

- **Repository evidence wins** over upstream skill assumptions.
- `docs/statistical_model.md` governs classification mathematics.
- Purposeful testing philosophy; no ceremonial full-suite runs.
- PostgreSQL only when technically implicated; no live Neon for dev checks.
- No automatic frontend work when out of scope.
- No Jira/Git internals in user-facing Admin copy.

The selected skills do not conflict heavily with these rules. One concrete
note:

- `code-review/SKILL.md` refers to `docs/agents/issue-tracker.md`, an artifact
  of the full upstream `mattpocock/skills` setup (which was **not** installed).
  In this repository, the originating spec source is `context.md` plus the
  Jira ticket references in commit/branch history — treat
  `docs/agents/issue-tracker.md` as absent and fall back to those sources.

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
    phrases, fact-preservation, rewrite examples, rubric, packs, voice)
  - `.agents/skills/unslop/presets/` (crisp, warm, expert, story)
  - `.agents/skills/unslop/scripts/` (Python helpers; 5 retain their
    executable bit)
- Modified locally: **No** (byte-identical to upstream).

### mattpocock/skills (eight selected skills)

- Upstream: <https://github.com/mattpocock/skills>
- Pinned commit: `1bb95954ef0d06ba4d64a9c267fb75f57c614a1f`
- License: MIT (Copyright (c) 2026 Matt Pocock)

| Skill | Upstream path | Local path | Supporting files imported |
|-------|---------------|------------|---------------------------|
| `diagnosing-bugs` | `skills/engineering/diagnosing-bugs/` | `.agents/skills/diagnosing-bugs/` | `scripts/hitl-loop.template.sh` |
| `code-review` | `skills/engineering/code-review/` | `.agents/skills/code-review/` | — |
| `domain-modeling` | `skills/engineering/domain-modeling/` | `.agents/skills/domain-modeling/` | `ADR-FORMAT.md`, `CONTEXT-FORMAT.md` |
| `codebase-design` | `skills/engineering/codebase-design/` | `.agents/skills/codebase-design/` | `DEEPENING.md`, `DESIGN-IT-TWICE.md` |
| `research` | `skills/engineering/research/` | `.agents/skills/research/` | — |
| `handoff` | `skills/productivity/handoff/` | `.agents/skills/handoff/` | — |
| `writing-for-agents` | `skills/productivity/writing-for-agents/` | `.agents/skills/writing-for-agents/` | `SKILL-MECHANICS.md` |
| `wizard` | `skills/engineering/wizard/` | `.agents/skills/wizard/` | `template.sh` |

- Modified locally: **Yes** — `code-review/SKILL.md` only. Its upstream
  frontmatter used an unquoted `description` containing `axes: Standards` (a
  colon followed by a space), which is invalid YAML and broke skill discovery.
  The description was re-encoded as a folded block scalar (`>-`); the text is
  unchanged. All other seven skills remain byte-identical to upstream.
- The per-skill `agents/openai.yaml` files were **omitted** — they are OpenAI
  platform metadata (`display_name` / `short_description`) not referenced by
  any `SKILL.md` and not part of the Zed Agent Skills format.
- All other `mattpocock/skills` skills (e.g. `tdd`, `implement`, `to-spec`,
  `to-tickets`, `prototype`, `grill-with-docs`, `wayfinder`,
  `improve-codebase-architecture`, `resolving-merge-conflicts`, `ask-matt`,
  `triage`, `teach`, `to-questionnaire`, `wait-what`, generic grilling and
  in-progress/deprecated skills) were **not** imported.

### browser-interaction-engineering

- Authored locally for SBGC-192. Not vendored from an upstream repository.
- Path: `.agents/skills/browser-interaction-engineering/SKILL.md`.
- Motivation: the SBGC-191 infinite-carousel incident (see
  `docs/postmortems/SBGC-191-infinite-carousel.md`) exposed that browser
  interaction work needs explicit risk classification, real-browser ground
  truth, harness qualification, and a two-strike stop-loss.

## Intentionally omitted (all sources)

- `.git/`, upstream GitHub Actions, issue/PR templates, `.gitignore`, and
  package/release metadata (`package.json`, lockfiles, changesets).
- Upstream repo-level docs and agent files not required by a selected skill
  (`AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, `README.md`, `CONTRIBUTING.md`,
  `CHANGELOG.md`, `docs/`, `scripts/` at the repo root).
- `unslop` `evals/`, `plans/`, `assets/`, and `docs/` (eval/maintenance
  machinery).
- `mattpocock/skills` unrelated skills and the OpenAI `agents/openai.yaml`
  metadata.

## Security / supply-chain note

- All imported scripts/templates were inspected before commit.
- No credential harvesting, no secrets, and no executable binary blobs.
- `unslop/scripts/wiki_sync.py` is the only network-calling helper
  (`https://en.wikipedia.org/w/api.php`), and only for the explicit
  maintenance "wiki sync" task — not normal operation and not auto-enabled.
- `wizard/template.sh` writes `.env` and invokes `gh secret`/`gh variable` and
  a browser opener, but only as an explicitly authored, human-driven wizard —
  no automatic mutation, and no network beyond those user-initiated actions.
- `diagnosing-bugs/scripts/hitl-loop.template.sh` is a passive prompt/capture
  loop (no network, no writes beyond reading terminal input).
- No upstream automatic mutation or internet-sync behavior is enabled.

## How to update

1. Re-clone (or `git fetch`) the upstream repository.
2. Record the new `git rev-parse HEAD` SHA.
3. Re-copy the specific paths listed above into `.agents/skills/<name>/`,
   preserving executable bits (`cp -p` / `cp -a`).
4. Diff against the vendored copy and review before replacing.
5. Update this file's pinned commit SHA.

Do **not** run an upstream maintenance/sync command (e.g. `wiki_sync.py`) or a
wizard merely because it exists. Updating is a deliberate, reviewed action.
