# Scripts

This folder contains simple, documented helper scripts that operate across the monorepo.

## Guidelines

- **App-specific logic** (build steps, test runners, deployment helpers) belongs inside the relevant `apps/` directory, not here.
- Scripts must remain **simple and self-contained** — if a script grows complex enough to require its own dependencies or tests, it likely belongs in an app or a dedicated tool package.
- Every script must include a brief **comment or docstring** explaining its purpose, inputs, and expected output.

### `update-skills-context.py`

Synchronises the auto-generated context-sources section of `skills.md` with the canonical `context.md` and archived context. Run via:

```bash
npm run update:skills-context
```

The generated section in `skills.md` is marked with `<!-- BEGIN/END GENERATED CONTEXT SOURCES -->` — **do not edit it manually**.
