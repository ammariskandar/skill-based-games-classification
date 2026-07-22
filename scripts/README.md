# Scripts

This folder contains simple, documented helper scripts that operate across the monorepo.

## Guidelines

- **App-specific logic** (build steps, test runners, deployment helpers) belongs inside the relevant `apps/` directory, not here.
- Scripts must remain **simple and self-contained** — if a script grows complex enough to require its own dependencies or tests, it likely belongs in an app or a dedicated tool package.
- Every script must include a brief **comment or docstring** explaining its purpose, inputs, and expected output.
- No scripts are required at this stage of the project.
