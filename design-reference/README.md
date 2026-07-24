# Design Reference

> **LOCKED REFERENCE — DO NOT EDIT, BUILD, IMPORT, OR DEPLOY.**

This directory contains immutable design-reference exports. Files here are not part of the production Astro application.

## Contents

| Directory / File           | Description                                      |
| -------------------------- | ------------------------------------------------ |
| `figma-make-dark-ui/`      | SBGC-136 Figma Make React/Vite dark-mode prototype |

## `figma-make-dark-ui/`

A generated React/Vite prototype exported from Figma Make (SBGC-136). It is:

- **Not** the production Astro application.
- **Not** importable by `apps/frontend` source code.
- **Not** built or deployed by Vercel (Vercel root is `apps/frontend`).
- **Not** a source of installable project dependencies.

It is useful as **implementation reference** for:

- layout and spacing patterns
- typography intent and hierarchy
- component appearance and structure
- interaction intent (hover states, transitions, expand/collapse behaviour)
- visual hierarchy and content grouping
- copy and labelling
- asset reference (images, icons)

### Rules

1. **Do not modify** any file inside this directory.
2. **Do not run** `npm install`, `pnpm install`, or any build command here.
3. **Do not import** its React components or styles into Astro.
4. The `package.json` and `pnpm-lock.yaml` inside are **archival only** — they document the original prototype's dependency set but must not influence the production project.
5. Production implementation must be **manually recreated** in Astro + Tailwind CSS, using the reference as a visual guide, not a copy-paste source.

### Source-of-truth hierarchy for design

1. Figma Make design (SBGC-136)
2. Jira-attached PNG mockup
3. This archived generated export (`design-reference/figma-make-dark-ui/`)

Deviations between production UI and this reference must be intentional and documented.
