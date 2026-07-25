# Reviews

This directory holds read-only software development review artefacts. Each review is a historical governance record, not a working document.

## Purpose

Periodic independent audits of the repository covering product alignment, architecture, code quality, security, testing, CI, dependencies, documentation, and maintainability. The reviewer is strictly read-only — it analyses and reports but never modifies.

## Jira-to-File Mapping

| Review File      | Jira Task    |
| ---------------- | ------------ |
| `review1.txt`    | SBGC-139     |
| `review2.txt`    | SBGC-140     |
| `review3.txt`    | SBGC-141     |
| `review4.txt`    | SBGC-142     |
| `review5.txt`    | SBGC-143     |
| `review6.txt`    | SBGC-144     |

## Immutable Historical-Review Policy

- Once a review is saved and committed, it becomes an immutable historical record.
- Review files MUST NOT be silently rewritten, edited, or cleaned up.
- Corrections or updates to previous findings are handled by:
  - an **addendum** appended to the current review; or
  - a **later review** that explicitly references and supersedes the earlier finding.
- Do not retroactively alter `reviewX.txt` to make it look more favourable or to hide past findings.

## Workflow

1. **Reviewer** (Codex in VS Code) analyses the repository in read-only mode.
2. The reviewer outputs its full report to the conversation.
3. The **user or implementation agent** copies the reviewer's output verbatim and saves it as `reviews/reviewX.txt`.
4. The reviewer does **not** write the file itself.
5. The owner triages findings and creates separate Jira remediation tasks where needed.
6. The review artefact is committed to the repository for project history.

## Reviewer Boundary

The reviewer (`codex.md`) is read-only. It MUST NOT:

- edit or create repository files;
- modify source code or documentation;
- generate or apply patches;
- install dependencies;
- stage, commit, merge, push, or create pull requests.

If asked to perform any write action, the reviewer refuses and continues only with analysis.
