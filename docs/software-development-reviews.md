# Software Development Reviews

Periodic independent audits of the repository covering product alignment, architecture, code quality, security, testing, CI, dependencies, documentation, and maintainability.

## Reviewer Identity

The reviewer is defined in [`codex.md`](../codex.md). It is a **read-only** senior software development auditor. Currently Codex in VS Code serves this role; the specification is agent-agnostic.

## When to Review

Reviews are recommended:

- after major milestones;
- before major phase transitions;
- before release;
- after significant remediation work;
- not on arbitrary calendar timing.

## Workflow

### 1. Preparation

```bash
cd /home/ammaris/projects/skill-based-games-classification
git switch main
git pull
```

Ensure the working tree is clean and all recent merges are reflected.

### 2. Select Review Ticket and Number

Choose the next review from the Jira mapping:

| Review | Jira    |
| ------ | ------- |
| 1      | SBGC-139 |
| 2      | SBGC-140 |
| 3      | SBGC-141 |
| 4      | SBGC-142 |
| 5      | SBGC-143 |
| 6      | SBGC-144 |

### 3. Collect Commit/PR Range

Determine the range of commits and merged PRs to review — typically everything since the last review, or the full history for the first review.

### 4. Open VS Code (Reviewer)

Open the repository in VS Code where Codex is configured as the reviewer. Load `codex.md` as the reviewer instruction set.

### 5. Read-Only Evidence Gathering

The reviewer inspects:

- `context.md`, `codex.md`, `skills.md`, `README.md`
- relevant `docs/` files
- source code, configuration, dependency manifests, lockfiles
- tests, CI definitions
- Git history, commits, merged PRs
- previous reviews (`reviews/review*.txt`)
- Jira references in repository history

The reviewer does not modify any file.

### 6. Reviewer Response

The reviewer outputs its full report following the structure defined in [`reviews/review-template.txt`](../reviews/review-template.txt). Each finding follows the required template with ID, severity, area, evidence, impact, action, confidence, and type.

### 7. Save Reviewer Output Verbatim

The user or implementation agent copies the reviewer's output verbatim and saves it as `reviews/reviewX.txt`. The reviewer does not write the file itself.

### 8. Verify Reviewer Changed Nothing

```bash
git status --short
```

Expected: no changes from the reviewer. Only the manually saved `reviews/reviewX.txt` should appear as a new file.

### 9. Owner Triage

The project owner reviews findings and decides:

- which findings to accept and act on;
- which to defer;
- which to reject with documented rationale.

Findings are advisory until accepted by the owner.

### 10. Create Remediation Jira Tasks

For accepted findings, create separate Jira remediation tasks. Do not bundle unrelated remediation into a single ticket unless they are genuinely coupled.

### 11. Commit the Review Artefact

```bash
git add reviews/reviewX.txt
git commit -m "SBGC-13X save review X artefact"
```

Review files become immutable historical records. Do not silently rewrite them.

## Historical Policy

- Review files are **immutable historical governance records**.
- Corrections are handled by addendum in a later review, not by editing past files.
- All reviews remain in the repository for future humans and LLMs to understand project evolution.
