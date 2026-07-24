---
name: djazztro-fullstack-engineering
summary: Agent-agnostic engineering skill for the Skill-Based Games Classification project using Astro, Tailwind CSS, Django, Django Ninja, and PostgreSQL.
description: Apply this skill whenever implementing, modifying, reviewing, testing, debugging, documenting, or deploying this project's monorepo. It defines the required engineering workflow, architectural boundaries, quality standards, security expectations, data rules, and stack-specific practices for AstroJS, Tailwind CSS, Django, Django Ninja, and PostgreSQL. Read context.md before acting.
version: 1.0.0
status: canonical
owners:
  - Ammar Iskandar
applies_to:
  - implementation
  - refactoring
  - debugging
  - testing
  - code review
  - database changes
  - API changes
  - frontend work
  - backend work
  - deployment preparation
  - technical documentation
---

# Djazztro Full-Stack Engineering Skill

## 1. Purpose

This skill governs coding-agent behaviour for the **Project Skill-Based Games Classification** repository.

The coding agent is an implementation specialist. It converts approved product decisions, Jira work, architecture, and acceptance criteria into maintainable software. It does not independently redefine the product, replace the architecture, expand scope, or silently reinterpret ambiguous requirements.

The project stack is informally called **Djazztro**:

- **D**jango for the backend, domain logic, administration, security, and data access;
- Django **Ninja** for the REST API;
- **A**stroJS for the frontend and server-rendered multi-page application;
- Tailwind CSS for styling;
- PostgreSQL for persistent relational data.

This skill is agent-agnostic. The instructions apply equally to any capable coding agent, IDE agent, command-line agent, or autonomous engineering system.

---

## 2. Mandatory source-of-truth order

Before changing the repository, consult sources in this order:

1. `context.md` at the repository root.
2. The currently assigned Jira issue and its acceptance criteria.
3. Accepted architecture decision records, if present.
4. Existing tests that express intentional behaviour.
5. Existing implementation and configuration.
6. Diagrams and supporting documentation.
7. Historical discussion only when explicitly supplied.

`context.md` defines the product and architectural baseline. Jira defines the unit of delivery and execution status. Code describes implemented reality but does not automatically override approved decisions.

When sources conflict:

- stop before making a material architectural or product decision;
- describe the conflict clearly;
- identify the smallest decision needed from the product owner or technical lead;
- do not silently select the easiest interpretation;
- do not let accidental legacy behaviour become a permanent requirement.

A coding agent MUST NOT claim that work is complete when implementation differs from `context.md` without recording the deviation.

<!-- BEGIN GENERATED CONTEXT SOURCES -->
This section is **auto-generated** by `scripts/update-skills-context.py`.
**Do not edit manually.**  Run `npm run update:skills-context` to refresh.

## Context documents

| Document                                                | Role               | SHA-256 (first 12 hex) |
| ------------------------------------------------------- | ------------------ | ---------------------- |
| `context.md`                                            | **Canonical**      | `165b01de1de0`       |
| `docs/archive/context-pre-reward-framework-2026-07-22.md` | Historical archive | `1a2d680ded5c`       |

## Mandatory reading rules

1. `context.md` is the **authoritative project baseline**.  Every agent
   MUST read it before implementing, reviewing, or modifying any part of
   the repository.
2. The archived context (`docs/archive/context-pre-reward-framework-2026-07-22.md`)
   is **historical reference only**.  It represents the state of the project
   before the dual-profile (Challenge / Reward) framework was introduced.
   Consult it only for historical investigation — it MUST NOT override or
   contradict the current `context.md`.
3. The canonical framework now contains **separate Challenge and Reward
   profiles**, each scored on **Micro**, **Mystiko**, and **Macro**
   dimensions.  The two profiles are related but remain conceptually and
   numerically independent.

<!-- END GENERATED CONTEXT SOURCES -->

---

## 3. Core project context

The application is a lightweight games database that classifies games using three percentages:

- **Micro**: execution and mechanics;
- **Mystiko**: hidden information, probability, mind games, reads, prediction, uncertainty, and short-horizon adaptation;
- **Macro**: systems knowledge, resource management, planning, and long-horizon strategy.

Every valid classification must satisfy:

- each score is within the permitted numeric range;
- Micro + Mystiko + Macro equals exactly 100;
- percentages describe skill composition, not difficulty.

The historical term **Meso** has been renamed to **Mystiko**. New code, schemas, API fields, labels, tests, and documentation should use `mystiko` unless an explicit compatibility requirement says otherwise. Do not introduce new `meso` identifiers casually.

The MVP is owner-curated and contains approximately 200 popular games. Most are identified by Steam App ID. A limited number of major non-Steam games may be manually created through Django Admin. DLC, demos, soundtracks, software, tools, and other non-game records must not appear in normal public listings.

Expected traffic is extremely low. Optimise for correctness, readability, low cost, low operational burden, and learning value—not hypothetical hyperscale.

---

## 4. Agent operating principles

### 4.1 Work from a bounded task

Every implementation session should have a specific Jira issue, approved task, or explicit instruction.

Before editing:

- restate the task internally;
- identify the affected application, modules, data, API, pages, tests, and documentation;
- inspect nearby implementation rather than assuming project conventions;
- identify dependencies and migration risk;
- determine how completion will be verified.

Do not implement unrelated improvements merely because they are attractive. Record them separately as observations or backlog suggestions.

### 4.2 Make the smallest coherent change

Prefer a complete vertical slice over scattered scaffolding, but keep the patch limited to the assigned outcome.

A good change:

- is understandable without reconstructing the agent's reasoning;
- follows existing project structure;
- adds tests at the correct level;
- updates documentation when behaviour or configuration changes;
- avoids speculative abstractions;
- leaves the repository runnable.

### 4.3 Do not overengineer

At the current scale, do not introduce any of the following without explicit approval:

- microservices;
- Redis;
- Celery or another task queue;
- Kubernetes;
- Elasticsearch or OpenSearch;
- GraphQL;
- a custom CMS;
- a separate administration frontend;
- a paid CDN;
- object storage for Steam images;
- event streaming;
- distributed tracing platforms;
- server-hosted LLM infrastructure;
- premature repository-wide design frameworks.

Use Django, PostgreSQL, ordinary HTTP, Astro rendering, and simple scheduled or manual operations.

### 4.4 Be explicit about uncertainty

Do not fabricate:

- API fields;
- provider behaviour;
- framework configuration;
- undocumented Steam guarantees;
- environment variables;
- database constraints;
- migration outcomes;
- test results;
- performance findings.

Inspect installed versions and official documentation when behaviour is version-sensitive.

---

## 5. Required engineering workflow

### Step 1 — Orient

Read:

- `context.md`;
- the assigned issue;
- relevant project README files;
- local agent instructions, if any;
- affected tests and modules.

Inspect the current repository tree before inventing paths.

### Step 2 — Plan

Create a concise implementation plan covering:

- files or modules expected to change;
- domain behaviour;
- API contract impact;
- database migration impact;
- frontend state and rendering impact;
- validation and security concerns;
- tests and verification;
- documentation updates.

For a trivial isolated edit, the plan may remain implicit. For migrations, API changes, cross-application work, security work, or deployment changes, it must be explicit.

### Step 3 — Implement incrementally

Work in small logical increments. After each meaningful increment:

- run the narrowest relevant checks;
- inspect errors rather than stacking speculative fixes;
- preserve existing behaviour outside the task;
- avoid broad automated rewrites unless required.

### Step 4 — Verify

Verification must be evidence-based. Run the applicable:

- formatter;
- linter;
- type checks;
- unit tests;
- API tests;
- integration tests;
- frontend tests;
- production build;
- Django system checks;
- migration checks;
- manual smoke checks.

Never state that tests passed unless they were actually run. If a check cannot be run, state why and identify the residual risk.

### Step 5 — Review the patch

Before finishing, inspect the final diff for:

- accidental files;
- secrets;
- debug output;
- dead code;
- duplicated logic;
- missing migrations;
- inconsistent naming;
- unjustified dependencies;
- inaccessible UI;
- stale documentation;
- changes outside scope.

### Step 6 — Report

A completion report should state:

- what changed;
- why it changed;
- important implementation decisions;
- migrations or configuration required;
- tests and checks run;
- known limitations;
- deviations from `context.md`, if any.

Do not pad reports with generic narration.

---

## 6. Monorepo standards

The project uses a monorepo. Follow the actual repository structure once established; do not impose a new layout during unrelated work.

Expected conceptual boundaries:

- frontend application: Astro and Tailwind CSS;
- backend application: Django and Django Ninja;
- root-level documentation and shared development configuration;
- deployment configuration scoped to the relevant application;
- no direct sharing of runtime source code between Python and TypeScript unless deliberately generated from a stable contract.

### 6.1 Monorepo rules

- Keep frontend and backend dependency systems separate and explicit.
- Keep root commands simple and discoverable.
- Do not require a heavyweight monorepo orchestrator solely because the repository contains two applications.
- Avoid duplicate environment variable definitions that can drift.
- Use application-local configuration where ownership is clear.
- Keep generated files out of source control unless they are intentionally canonical.
- Do not place secrets in repository configuration, examples, fixtures, screenshots, logs, or documentation.

### 6.2 Dependency discipline

Before adding a dependency:

- prove that the standard library or existing stack cannot reasonably solve the problem;
- confirm maintenance, licence suitability, and framework compatibility;
- assess bundle, startup, security, and operational cost;
- prefer mature, focused packages over broad frameworks;
- document why the dependency exists.

Do not add a library for trivial formatting, basic data transformation, a single utility class, or behaviour already supplied by Astro, Django, PostgreSQL, or the browser.

Pin dependencies according to the repository's chosen strategy and preserve lockfiles.

---

## 7. Architecture boundaries

### 7.1 Astro responsibilities

Astro owns:

- public pages and layouts;
- server-rendered presentation;
- page routing;
- lightweight interactive islands;
- frontend accessibility and responsive behaviour;
- server-side calls to Django;
- browser-side enhancements that genuinely require JavaScript;
- SEO and social metadata;
- Google Analytics integration when enabled.

Astro does not own:

- authoritative classifications;
- database access;
- Steam credentials;
- score validation as the sole authority;
- editorial permissions;
- game import business rules;
- final recommendation selection;
- moderation rules.

### 7.2 Django responsibilities

Django owns:

- domain models;
- business rules;
- database integrity;
- game identity and source handling;
- editorial classifications;
- Steam import and metadata refresh;
- content-type exclusion;
- administration;
- authentication and permissions when introduced;
- API behaviour;
- recommendation calculation in the final product;
- server-side validation;
- security-sensitive logic.

### 7.3 PostgreSQL responsibilities

PostgreSQL owns durable relational integrity where feasible:

- primary keys;
- unique constraints;
- foreign keys;
- check constraints;
- transactional consistency;
- indexes justified by actual query patterns.

Do not rely only on frontend validation or Django form validation for invariants that can be enforced safely in the database.

### 7.4 Steam responsibilities

Steam is an external metadata and image source for Steam games. The application stores only the minimum metadata needed for its own catalogue, search, filtering, and reliability.

The system must tolerate:

- missing fields;
- unavailable applications;
- non-game content;
- malformed or unexpected responses;
- timeouts;
- temporary failures;
- missing images.

Do not build public pages that require a successful live Steam request on every user visit if locally stored metadata already supports the page.

### 7.5 WebLLM boundary

WebLLM is post-MVP and optional.

Django/Python must determine recommended games and provide trusted structured reasons. Browser-local WebLLM may turn that data into readable prose. It must not become the source of recommendation truth, alter scores, invent evidence, or perform privileged server operations.

Load WebLLM only when the feature is requested. Do not burden ordinary pages with model downloads or GPU initialization.

### 7.6 Design reference assets

The Figma Make React/Vite prototype archived at `design-reference/figma-make-dark-ui/` (SBGC-136, archived by SBGC-137) is a **read-only design reference**. Agents MUST:

- inspect the reference export before implementing matching UI;
- treat every file under `design-reference` as immutable;
- never modify files inside that directory;
- never run package installation (`npm install`, `pnpm install`) inside it;
- never add its dependencies to the production project automatically;
- never import its React components, styles, or configuration into Astro;
- never include `design-reference` in production imports, build configuration, or deployment output;
- translate design intent into Astro components, Tailwind utilities, semantic HTML, and accessible interactions;
- preserve canonical MPA and SSR decisions when implementing from the reference;
- report design/architecture conflicts rather than resolving them silently.

---

## 8. AstroJS engineering standards

### 8.1 Application model

Treat the frontend as a **multi-page application**, not a single-page application.

Default approach:

- server-render or prerender pages as appropriate;
- use normal document navigation;
- hydrate only components that need browser interactivity;
- avoid SPA routing and global client state unless a future requirement proves they are necessary.

### 8.2 Rendering strategy

Use the least dynamic rendering mode that satisfies the page:

- prerender stable informational pages such as About, methodology, and static policy pages;
- render game detail, search, listings, and rankings on demand when they depend on current backend data;
- use client-side rendering only for focused interactions that cannot be handled effectively with HTML and server requests;
- use server islands only when delayed or independently dynamic content creates a measurable benefit.

Do not turn the entire application into client-rendered JavaScript for convenience.

### 8.3 Astro component rules

- Prefer `.astro` components for ordinary presentation.
- Introduce a UI framework only for a bounded interactive island that genuinely benefits from it.
- Keep data fetching at route or server-component boundaries rather than scattering requests across presentational components.
- Pass explicit, typed props.
- Keep components focused and composable.
- Avoid components whose only purpose is hiding a few static HTML elements.
- Keep domain names aligned with backend terminology.
- Do not expose server-only environment variables to the browser.

### 8.4 Data fetching

The Astro server should call the Django API through a dedicated client layer.

The client layer should provide:

- a single configured base URL;
- explicit timeouts;
- typed response boundaries;
- consistent error mapping;
- safe logging;
- no leaked credentials;
- clear distinction between not found, invalid request, upstream failure, and internal failure.

Do not call PostgreSQL directly from Astro.

Avoid duplicate backend calls within one render. Where appropriate, reuse already fetched data during the request.

### 8.5 Page behaviour

Every page must deliberately handle:

- normal data;
- empty data;
- missing classification;
- missing image;
- invalid route input;
- backend not found;
- backend timeout or failure;
- unexpected response shape.

Do not show raw exceptions or provider payloads to users.

### 8.6 Performance

The frontend should remain usable while a game is running in the background and on poor connections.

Therefore:

- minimise client JavaScript;
- avoid unnecessary hydration;
- do not ship large component libraries for basic UI;
- set image dimensions to reduce layout shift;
- lazy-load non-critical imagery where appropriate;
- avoid blocking third-party scripts;
- prefer semantic HTML over JavaScript simulations of native controls;
- keep CSS output lean;
- monitor actual build output before optimising blindly.

### 8.7 SEO and metadata

Public game pages and catalogue pages should have intentional:

- titles;
- descriptions;
- canonical URLs;
- social metadata;
- indexability rules;
- not-found status behaviour.

Do not create duplicate public URLs for the same game without canonicalisation or redirects.

---

## 9. Tailwind CSS engineering standards

### 9.1 Role of Tailwind

Tailwind is the primary styling system. Use it consistently rather than mixing several competing conventions.

The objective is a fast, sleek, modern, minimal, responsive UI—not a demonstration of every utility.

### 9.2 Styling principles

- Use a small, coherent design vocabulary.
- Reuse spacing, typography, radii, borders, and surface conventions.
- Prefer responsive layouts that naturally reflow.
- Keep component markup readable.
- Extract reusable components when patterns repeat semantically, not merely because class strings are long.
- Avoid arbitrary values when a standard design token works.
- Avoid deeply nested conditional class construction.
- Do not use colour as the only way to distinguish Micro, Mystiko, and Macro.

### 9.3 Micro/Mystiko/Macro visual system

The three dimensions need stable, distinguishable treatment across:

- game cards;
- game pages;
- rankings;
- search results;
- legends;
- charts or bars;
- administrative previews where useful.

Every visual representation must include readable text or numeric labels. Users with colour-vision deficiencies must still understand the result.

The agent must not invent permanent brand colours without an approved design decision. Follow existing tokens and components.

### 9.4 Component extraction

Extract a component when:

- it represents a reusable product concept;
- it appears in multiple contexts;
- it has meaningful variants;
- extraction improves consistency or testability.

Do not create a generic component system that obscures ordinary HTML.

### 9.5 Accessibility

Tailwind classes do not create accessibility by themselves.

Ensure:

- semantic landmarks and headings;
- associated labels for controls;
- visible focus indicators;
- keyboard-operable interactions;
- sufficient contrast;
- meaningful alternative text;
- accessible status and error messages;
- no hover-only critical information;
- reduced-motion respect where animation exists;
- sensible touch targets.

### 9.6 Dynamic classes

Do not construct class names in a way the build system cannot detect reliably. Use complete, statically discoverable class strings or an established mapping.

Do not permit user input or untrusted API data to become unrestricted CSS classes.

---

## 10. Django engineering standards

### 10.1 Domain-first structure

Organise Django around coherent domain responsibilities rather than arbitrary technical buckets.

Likely domains include:

- games;
- classifications;
- external integrations;
- public API;
- administration;
- future community submissions and recommendations.

Do not create an application for every model. Do not place all logic in one oversized application either.

### 10.2 Models

Models should express durable domain concepts and invariants.

The game model must distinguish at least:

- Steam versus manual source;
- external identifier where applicable;
- content type;
- listing or publication status;
- required manual metadata;
- timestamps and metadata freshness.

The editorial classification must maintain a one-to-one relationship with its game unless `context.md` is deliberately changed.

Use clear names, explicit choices, and constraints. Avoid generic JSON fields for data that has a stable relational shape.

### 10.3 Business logic placement

Use:

- model methods for behaviour intrinsic to one model;
- querysets or managers for reusable query semantics;
- services for workflows spanning models or external systems;
- schemas for API validation and serialization;
- admin classes for administration presentation and actions.

Avoid:

- large views containing all business logic;
- signals for core behaviour that should be explicit;
- hidden database writes during property access;
- duplicated validation across unrelated layers;
- circular dependencies between applications.

Signals may be used only when the decoupling is genuine and the behaviour remains easy to discover and test.

### 10.4 Validation

Validate at multiple appropriate boundaries:

- API/schema validation for client feedback;
- model validation for domain use outside the API;
- database constraints for durable invariants;
- admin/form validation for owner workflows.

The score-total rule must not exist only in client-side JavaScript.

Beware decimal and rounding behaviour. The chosen score type must allow exact enforcement of the total. Do not use floating-point arithmetic for an exact 100-total invariant.

### 10.5 Queries

- Prevent avoidable N+1 queries.
- Use relation loading deliberately.
- Keep public catalogue query logic centralised.
- Make exclusion of hidden and non-game records difficult to forget.
- Paginate catalogue and ranking endpoints.
- Add indexes only for actual filtering, ordering, joining, or uniqueness requirements.
- Inspect generated queries when performance or correctness is uncertain.

At the expected traffic level, clarity outranks micro-optimisation.

### 10.6 Transactions

Use transactions for workflows that must succeed or fail as one unit, such as:

- creating or updating related game and metadata records;
- applying administrative actions across related records;
- future approval plus aggregate recalculation;
- migrations that transform related data.

Do not wrap every read-only request in a transaction without reason.

### 10.7 Django Admin

Django Admin is the owner-facing CMS-equivalent and must be treated as a real operational interface.

Admin work should prioritise:

- useful list displays;
- search by name and external identifier;
- filters by source, content type, publication, and classification status;
- clear grouping of Steam and manual fields;
- safe bulk actions;
- readonly system fields;
- visible validation errors;
- confirmation for destructive operations;
- audit-relevant timestamps and editor information.

Do not build a separate admin frontend for MVP.

### 10.8 Settings

Separate environment-dependent settings cleanly. Production must not rely on development defaults.

Sensitive values must come from environment-managed secrets. Never commit:

- Django secret keys;
- database credentials;
- API credentials;
- private service URLs containing credentials;
- administrator credentials.

Production must use a production-grade application server rather than Django's development server.

### 10.9 Security

Preserve Django's security middleware and built-in protections. Configure rather than bypass them.

Review as applicable:

- `DEBUG`;
- allowed hosts;
- CSRF trusted origins;
- CORS allowlist;
- secure cookies;
- HTTPS forwarding and redirect behaviour;
- HSTS only when deployment is ready;
- content type sniffing protection;
- referrer policy;
- admin access;
- request body limits;
- password policy when accounts exist;
- rate limiting for sensitive endpoints.

Run Django's deployment checks against production settings before release.

---

## 11. Django Ninja API standards

### 11.1 API role

The API is the stable contract between Astro and Django. It should expose product resources and workflows, not database internals.

### 11.2 Contract rules

- Version the API path from the beginning.
- Use consistent naming and casing.
- Use `mystiko` in new contracts.
- Keep response shapes deliberate and documented.
- Return appropriate HTTP status codes.
- Distinguish validation, authentication, permission, not-found, conflict, upstream, and internal errors.
- Do not leak stack traces or sensitive provider details.
- Avoid breaking response changes without an explicit migration plan.

### 11.3 Schemas

- Define explicit input and output schemas.
- Do not return unbounded model serialization by convenience.
- Keep internal-only fields out of public responses.
- Represent optionality honestly.
- Validate route and query parameters.
- Cap pagination size.

### 11.4 Endpoint design

Prefer resource-oriented endpoints for:

- game detail;
- catalogue search and listing;
- rankings;
- future submissions and user data.

Administrative imports and refresh operations should remain protected and may live in Django Admin rather than public API endpoints.

### 11.5 Error format

Use one project-wide error envelope containing enough information for the frontend to present a useful message and for logs to correlate the failure. Do not expose internal exception text directly.

### 11.6 API documentation

Keep generated OpenAPI output usable, but treat it as a consequence of accurate schemas—not a substitute for product-level documentation.

---

## 12. PostgreSQL engineering standards

### 12.1 PostgreSQL is canonical production storage

Local development may use PostgreSQL as well to reduce environment differences. If SQLite is temporarily used for isolated local work, do not rely on behaviour that differs from production PostgreSQL.

### 12.2 Data integrity

Use appropriate:

- primary keys;
- foreign keys;
- unique constraints;
- non-null rules;
- check constraints;
- deletion behaviour;
- indexes.

Important examples include:

- uniqueness of source plus external identifier where an external identifier exists;
- one editorial classification per game;
- exact Micro/Mystiko/Macro total;
- valid score ranges;
- valid source-specific field combinations.

Remember that nullable values affect uniqueness semantics. Design constraints intentionally rather than assuming null behaves like an ordinary value.

### 12.3 Migrations

Every schema change must include a migration.

Before finishing migration work:

- inspect generated operations;
- consider existing data;
- separate schema and large data transformations when appropriate;
- ensure forwards migration succeeds;
- consider rollback limitations;
- verify no accidental destructive operation exists;
- update seed data and tests.

Never edit an already-applied shared migration merely to make history look cleaner. Add a new corrective migration.

### 12.4 Indexes

Index for actual access patterns such as:

- external identifier lookup;
- slug lookup;
- publication/content-type filtering;
- common ranking order;
- foreign-key joins;
- search strategy selected by the project.

Do not index every field. Each index has write and storage cost, even if cost is small at current scale.

### 12.5 Search

Begin with PostgreSQL-supported, maintainable search suitable for approximately 200 records. Do not introduce a dedicated search engine.

Case-insensitive name search, sensible ordering, and pagination are sufficient unless product evidence proves otherwise.

### 12.6 Backups and operational safety

Production data must be recoverable. Before destructive migrations or bulk imports:

- confirm backup or recovery options;
- avoid unreviewed mass deletion;
- make data population scripts repeatable where possible;
- log or report failed records clearly.

---

## 13. Steam integration standards

### 13.1 Encapsulation

All Steam communication must pass through a dedicated backend integration layer. Do not scatter provider-specific requests through views, models, admin classes, and templates.

### 13.2 Request behaviour

Implement:

- finite connect and read timeouts;
- bounded retries only for appropriate transient failures;
- response validation;
- safe error translation;
- no credentials in logs;
- deterministic handling of unavailable App IDs.

Avoid retry storms. User-facing requests must not hang indefinitely because Steam is slow.

### 13.3 Normalisation

Map external data into explicit internal concepts. Preserve the distinction between:

- game;
- DLC;
- demo;
- soundtrack;
- software;
- tool;
- unknown;
- any additional approved type.

Unknown data should be reviewable, not silently treated as a public game.

### 13.4 Images

Steam images should normally remain externally hosted and hotlinked from known returned or approved URLs. Provide a fallback for missing or failed images.

Do not introduce image downloads, object storage, transformations, or a paid image CDN during MVP without explicit approval.

### 13.5 Refresh

Metadata refresh must be explicit, safe, and idempotent enough for owner use. A refresh must not overwrite editorial classification or manual owner decisions unrelated to Steam metadata.

Track refresh status or timestamp when useful for diagnosis.

### 13.6 Testing

Automated tests must not depend on live Steam availability. Mock or fake provider responses at the integration boundary. Keep a small manual verification path for real integration testing.

---

## 14. Manual non-Steam game standards

Manual records exist for a small, curated set of very popular games not adequately represented by Steam, such as Valorant.

Manual records must:

- be created and maintained by authorised owners through Django Admin;
- store the metadata needed for public display and search;
- support an approved external image URL or fallback;
- participate in classifications, listings, search, and rankings like Steam games;
- never trigger Steam refresh logic;
- remain clearly distinguishable by source internally.

Do not turn manual records into an unrestricted crowd-sourced database during MVP.

---

## 15. Classification implementation standards

### 15.1 Canonical names

Use:

- `micro`;
- `mystiko`;
- `macro`.

Do not use vague aliases such as `skill1`, `mid`, or `strategy_score`.

### 15.2 Numeric representation

Choose a representation that supports exact totals and the approved precision. For MVP, whole-number percentages are simplest unless `context.md` explicitly authorises decimal editorial scores.

Do not use binary floating point for exact validation.

### 15.3 Derived values

Dominant category and tie behaviour must be deterministic and shared. Do not independently recalculate with different rules in backend and frontend.

Prefer the backend returning authoritative derived values when they affect product semantics. The frontend may format them visually.

### 15.4 Editorial notes

Notes should explain material ambiguity, assumptions, or play-level context. They are not a place for unbounded rich-text or arbitrary HTML.

### 15.5 Future community data

Do not prematurely merge community submission fields into editorial records. Future submissions, moderation states, and aggregates should have their own models and auditability.

Editorial and community scores must remain separate.

---

## 16. Search, listings, and rankings standards

### 16.1 Public eligibility

Centralise the definition of a publicly eligible game. Normal public queries should not repeatedly reimplement exclusions.

A public game should generally be:

- published or listed;
- of an allowed game content type;
- not hidden;
- not a DLC, demo, soundtrack, software product, tool, or invalid record.

Whether an unclassified game appears must follow the specific page requirement.

### 16.2 Search

Search should:

- be case-insensitive;
- handle empty and whitespace input predictably;
- use bounded query lengths;
- preserve query state in the URL;
- return stable pagination;
- avoid exposing hidden records;
- produce a useful no-results state.

### 16.3 Rankings

Rankings must:

- use authoritative stored classifications;
- define tie ordering;
- exclude ineligible records;
- be stable across pagination;
- support Micro, Mystiko, and Macro consistently;
- avoid presenting an unclassified game as a zero-score game.

### 16.4 Filtering

Filters should be composable, URL-addressable, and validated. Unsupported values should not create server errors.

---

## 17. Security and abuse standards

### 17.1 Defence layers

Hosting providers handle a portion of network-level abuse. Application code must still handle:

- brute force;
- abusive search traffic;
- malformed requests;
- oversized payloads;
- automated submissions when community features arrive;
- authentication attacks;
- unauthorised administration;
- injection attempts;
- unsafe external content.

### 17.2 Secrets

Use provider-managed environment variables for production secrets and ignored local environment files for development.

The frontend may only expose variables explicitly intended for browsers. A variable name suggesting public exposure must never contain a secret.

### 17.3 CORS and CSRF

CORS must be an allowlist, not a convenience wildcard. CSRF protection must remain enabled for cookie-authenticated state-changing requests.

Do not confuse CORS with authentication or CSRF protection.

### 17.4 Rate limiting

Rate-limit endpoints based on risk, not merely all routes equally. Sensitive candidates include:

- login;
- password reset;
- registration;
- future score submission;
- search;
- protected import or refresh operations.

Keep limits configurable and avoid introducing Redis solely for MVP throttling unless the selected implementation genuinely requires it and is approved.

### 17.5 Admin

A non-default admin path is only a minor noise reduction, not the primary security control. Rely on strong authentication, limited accounts, HTTPS, secure settings, and monitoring.

### 17.6 Logging hygiene

Never log:

- passwords;
- secret keys;
- database credentials;
- full authentication tokens;
- sensitive cookies;
- raw personal data without need;
- complete upstream payloads containing sensitive fields.

---

## 18. Testing strategy

Testing should be proportionate but real.

### 18.1 Backend tests

Cover:

- model constraints;
- source-specific validation;
- score total and ranges;
- content-type exclusion;
- query helpers;
- API success and failure responses;
- permissions;
- Steam integration normalisation and failures;
- admin workflows where custom behaviour exists;
- migrations when data transformation is nontrivial.

### 18.2 Frontend tests

Cover high-value behaviour:

- score visualisation;
- normal, empty, and error states;
- search and filter parameters;
- game page rendering from API responses;
- accessibility of interactive components;
- client islands only where their logic warrants tests.

Do not test Astro or Tailwind themselves.

### 18.3 Integration tests

Verify the contract between Astro and Django using representative responses. Test status mapping and malformed or partial upstream data.

### 18.4 End-to-end tests

Keep a small critical suite for:

- catalogue browsing;
- searching;
- opening a game;
- viewing a classification;
- using rankings and filters;
- owner creation/import and classification through the supported admin workflow, when feasible.

Do not build a huge brittle E2E suite for 100 monthly visits.

### 18.5 Test data

Use small, readable factories or fixtures representing:

- a valid Steam game;
- a valid manual game;
- DLC/non-game content;
- hidden content;
- classified and unclassified records;
- tied and extreme classifications;
- failed or incomplete Steam metadata.

Do not make tests depend on the complete 200-game production catalogue.

### 18.6 Regression rule

Every bug fix should add or update a test that would fail before the fix, unless automation is genuinely impractical. Explain exceptions.

---

## 19. Quality gates

A task is not complete until applicable gates pass.

### 19.1 Universal gates

- scope matches the assigned issue;
- repository contains no secrets or debug debris;
- formatting and linting pass;
- relevant tests pass;
- names follow Micro/Mystiko/Macro terminology;
- documentation reflects behavioural or operational changes;
- final diff has been reviewed.

### 19.2 Frontend gates

- Astro production build succeeds;
- pages render without avoidable client JavaScript;
- responsive behaviour is checked;
- keyboard and basic accessibility behaviour are checked;
- error and empty states exist;
- no server secrets appear in built client assets.

### 19.3 Backend gates

- Django checks pass;
- production deployment checks are reviewed before release;
- migrations are present and inspected;
- API schemas match implementation;
- validation exists at the right layers;
- query count is reasonable for affected endpoints;
- external requests have timeouts.

### 19.4 Database gates

- constraints represent approved invariants;
- migrations work on existing data assumptions;
- destructive changes are explicit;
- indexes have a reason;
- rollback and recovery implications are understood.

---

## 20. Observability and analytics

Use simple, provider-native observability for MVP:

- Django/backend logs on Render;
- Astro/SSR and deployment logs on Vercel;
- database monitoring supplied by Neon;
- Google Analytics for product usage when enabled;
- a basic health endpoint and optional free uptime check.

Do not add SigNoz to the current architecture.

Logs should answer:

- what failed;
- where it failed;
- which request or operation was involved;
- whether Steam, Django, PostgreSQL, or Astro was responsible;
- what action an owner can take.

Analytics must not become a hidden source of critical application behaviour.

---

## 21. Deployment standards

Target services:

- Vercel for Astro;
- Render for Django;
- Neon for PostgreSQL.

Plans and provider details can change. Inspect current provider documentation and repository configuration before deployment work.

### 21.1 Deployment expectations

- environment variables are configured per environment;
- frontend points to the correct backend URL;
- backend allows only intended hosts and origins;
- database connections use production credentials and required transport security;
- migrations run through an explicit controlled process;
- Django static assets for Admin are collected and served correctly;
- health checks reflect backend readiness sufficiently for this project;
- cold starts are accepted and handled gracefully;
- preview environments do not mutate production data.

### 21.2 Release safety

Before production release:

- run build and test gates;
- verify configuration without printing secrets;
- test Astro-to-Django connectivity;
- test Django-to-PostgreSQL connectivity;
- test a real Steam lookup or refresh through the intended owner workflow;
- verify manual game display;
- verify exclusions;
- verify Admin access;
- verify error pages and logs;
- record known issues.

---

## 22. Documentation standards

Documentation is part of implementation.

Update relevant material when changing:

- architecture;
- domain terminology;
- environment variables;
- setup commands;
- API contracts;
- models or migrations;
- deployment processes;
- administration workflows;
- provider assumptions;
- security controls.

### 22.1 `context.md`

Do not rewrite `context.md` casually. Update it when an approved material decision changes. Record deviations and preserve decision history.

### 22.2 README files

README content should enable a new engineer or agent to:

- understand the application boundary;
- install dependencies;
- configure local environment variables;
- run frontend and backend;
- migrate and seed the database;
- run checks and tests;
- understand deployment ownership.

### 22.3 Comments

Comments should explain why, constraints, or non-obvious risk. Do not narrate obvious syntax. Remove stale comments during related changes.

### 22.4 Decision records

Use an architecture decision record when a change has lasting consequences, meaningful alternatives, or migration cost. Examples include authentication approach, schema identity strategy, recommendation similarity formula, or a change to rendering architecture.

---

## 23. Code review protocol

When reviewing code, check in this order:

1. Product correctness against `context.md` and Jira.
2. Security and data integrity.
3. Architectural boundaries.
4. Error handling and failure behaviour.
5. Tests and evidence.
6. Maintainability and naming.
7. Performance proportional to current scale.
8. Style.

Classify findings by severity:

- **Blocker**: data loss, security vulnerability, broken core behaviour, impossible deployment, or direct contradiction of an approved requirement.
- **Major**: likely user-visible failure, integrity gap, broken API contract, missing migration, or substantial maintainability risk.
- **Minor**: limited defect or inconsistency worth correcting.
- **Suggestion**: optional improvement that should not block the task.

Do not inflate stylistic preferences into blockers. Do not approve code merely because it runs locally.

---

## 24. Refactoring rules

Refactor when it directly supports the assigned task, fixes a demonstrated problem, or has explicit approval.

A refactor must:

- preserve behaviour unless change is approved;
- have regression coverage;
- reduce complexity or duplication measurably;
- avoid mixing widespread renaming with behavioural changes when possible;
- avoid replacing stable framework conventions with custom abstractions.

Do not perform repository-wide cleanup during a small feature ticket.

---

## 25. Prohibited shortcuts

The coding agent must not:

- skip `context.md`;
- use Meso in new canonical interfaces without a compatibility reason;
- trust client-side validation as authoritative;
- access PostgreSQL directly from Astro;
- place Steam or database secrets in client code;
- expose raw exceptions;
- call Steam without timeouts;
- rely on live Steam in automated tests;
- make DLC exclusion a fragile title-keyword check only;
- silently blend editorial and future community scores;
- let WebLLM select recommendations;
- introduce infrastructure outside the approved architecture;
- claim checks passed without running them;
- mark work complete with uncommitted migrations or undocumented environment changes;
- edit unrelated files to make the diff appear cleaner;
- generate enormous abstraction layers for a small application;
- replace Django Admin with a custom interface during MVP;
- add SigNoz, Redis, Celery, Kubernetes, or a paid CDN without explicit approval.

---

## 26. Decision heuristics

When several valid implementations exist, prefer the option that:

1. follows framework conventions;
2. preserves the Astro/Django boundary;
3. enforces integrity closest to the data;
4. is easiest for a future human to understand;
5. minimises operational services;
6. has the smallest client-side JavaScript cost;
7. is testable without live third parties;
8. is reversible;
9. serves current requirements rather than hypothetical scale;
10. remains portable across comparable hosting providers.

---

## 27. Task completion template

Use this structure for implementation summaries:

### Outcome

State the delivered user or owner capability.

### Changes

Summarise the meaningful frontend, backend, database, configuration, and documentation changes.

### Validation

List the checks and tests actually run and their results.

### Deployment or migration notes

State required migrations, environment variables, commands, provider changes, or release sequencing.

### Remaining risks or deviations

State known limitations, deferred work, and any divergence from `context.md`.

Omit empty sections only when genuinely irrelevant.

---

## 28. Activation examples

This skill applies when the task involves any of the following:

- implementing a Jira issue in the SBGC project;
- creating or changing an Astro route or component;
- styling the application with Tailwind CSS;
- creating Django models, services, admin workflows, or Ninja endpoints;
- creating PostgreSQL migrations or constraints;
- integrating Steam metadata;
- implementing search, listings, filters, rankings, or game pages;
- adding tests, logging, security controls, or deployment configuration;
- reviewing a pull request against project requirements;
- debugging a cross-stack issue;
- documenting implementation or deviations.

This skill does not authorise independent changes to product strategy, terminology, scoring methodology, infrastructure, or final-product scope.

---

## 29. Maintainer note

This skill should remain focused on **how the coding agent engineers this project**. Product history, full scope, architecture rationale, Jira inventory, and long-form methodology belong in `context.md` and linked decision records.

When this file becomes excessively large due to framework-specific detail, retain the cross-stack rules here and move stable deep references into a nearby `references/` directory. The skill should remain discoverable, operational, and precise rather than becoming a duplicate of every framework manual.
