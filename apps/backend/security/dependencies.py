"""
Architectural tech stack & dependency registry — SBGC-108.

This is a *curated, architectural catalog* maintained manually by engineering
staff.  It is intentionally decoupled from raw dynamic lockfile parsing so it
can describe full-system components that never appear in a manifest — the
``smtp4dev`` Docker container, Python standard-library modules (``ipaddress``),
and PostgreSQL as a system prerequisite — alongside manifest-declared packages.

Lifecycle status reflects architectural intent (Core / Required / Dev tool /
Under evaluation / Deprecated), never a static CVE claim: dynamic vulnerability
state belongs to the CI audit gates (``pip-audit`` / ``npm audit``).

Maintenance contract:
- Every package pinned in ``apps/backend/requirements.txt`` and every runtime
  dependency in ``apps/frontend/package.json`` must have a matching entry here
  (enforced by ``security.tests.test_dependency_registry``).  Adding a new
  manifest dependency without an architectural entry fails the test suite.
- ``version_spec`` mirrors the manifest pin for manifest packages, or the
  supported architectural window for core components.

Django version constraint ``>=5.2,<6.1``: Django 5.2 is the supported LTS line
and Django 6.0 is the current feature release in use.  The upper bound ``<6.1``
strictly prevents unvetted minor upgrades into 6.1, where deprecated APIs are
scheduled for removal and third-party ASGI/routing extensions (specifically
``django-ninja``) have not yet established verified release compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Ecosystem(StrEnum):
    """Coarse dependency grouping by runtime boundary."""

    BACKEND_CORE = "Backend (Python / Django)"
    BACKEND_SERVICE = "Backend Service / Worker"
    FRONTEND_CORE = "Frontend (Node / Astro)"
    FRONTEND_UI = "Frontend (UI / Styling)"
    INFRA_DEVOPS = "Infrastructure & Tooling"


class LifecycleStatus(StrEnum):
    """Architectural lifecycle status — never a static CVE claim."""

    CORE = "Core Runtime"
    REQUIRED = "Production Required"
    DEV_TOOL = "Development & CI Tool"
    REVIEW_REQUIRED = "Under Evaluation"
    DEPRECATED = "Scheduled for Removal"


@dataclass(frozen=True)
class DependencyItem:
    """One entry in the architectural dependency catalog."""

    name: str
    version_spec: str
    ecosystem: Ecosystem
    affects_subsystem: str
    lifecycle_status: LifecycleStatus
    alternatives: str
    justification: str


TECH_STACK_REGISTRY: tuple[DependencyItem, ...] = (
    # ── Backend core & API ───────────────────────────────────────────────────
    DependencyItem(
        name="django",
        version_spec=">=5.2,<6.1",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem=(
            "Core ORM, Admin Interface, Session Engine, DatabaseCache, "
            "SecurityMiddleware"
        ),
        lifecycle_status=LifecycleStatus.CORE,
        alternatives="FastAPI, Litestar, Flask",
        justification=(
            "Provides complete session authentication, robust administrative "
            "UI, and built-in database-backed caching without extra "
            "dependencies.  Constrained to >=5.2,<6.1: 5.2 is the supported "
            "LTS line and 6.0 the current feature release; <6.1 blocks "
            "unvetted minor upgrades where deprecated APIs are removed and "
            "django-ninja compatibility is unverified."
        ),
    ),
    DependencyItem(
        name="django-ninja",
        version_spec=">=1.3.0",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem=(
            "REST API routing (/api/v1/auth/*, /api/v1/games/*, /api/v1/rankings/*)"
        ),
        lifecycle_status=LifecycleStatus.CORE,
        alternatives="Django REST Framework (DRF), FastAPI",
        justification=(
            "Provides native Pydantic schema validation and OpenAPI schema "
            "generation directly within Django without intermediate "
            "serializers."
        ),
    ),
    DependencyItem(
        name="pydantic",
        version_spec=">=2.0.0",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem=(
            "API input/output schema validation and serialization across Ninja routers"
        ),
        lifecycle_status=LifecycleStatus.CORE,
        alternatives="msgspec, marshmallow, attrs",
        justification=(
            "Performs runtime type validation and coercion for API boundary "
            "schemas, matching Django Ninja type contracts."
        ),
    ),
    DependencyItem(
        name="pydantic_core",
        version_spec="==2.46.4",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem=(
            "Compiled engine implementing pydantic v2 validation primitives"
        ),
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="N/A (companion to pydantic)",
        justification=(
            "Rust-compiled core distribution required by pydantic v2; "
            "installed as its binary wheel."
        ),
    ),
    DependencyItem(
        name="psycopg",
        version_spec=">=3.2.0",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem=(
            "PostgreSQL database adapter, DatabaseCache concurrency, "
            "transaction handling"
        ),
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="asyncpg, psycopg2-binary",
        justification=(
            "Modern PostgreSQL driver supporting binary data transfers, "
            "connection pooling, and pip-installable binary wheels."
        ),
    ),
    DependencyItem(
        name="psycopg-binary",
        version_spec="==3.3.4",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem="PostgreSQL client adapter binary wheel distribution",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="N/A (companion to psycopg)",
        justification=(
            "Precompiled binary wheel of the psycopg driver installed on "
            "deployment platforms without a local compiler."
        ),
    ),
    DependencyItem(
        name="asgiref",
        version_spec="==3.12.1",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem="Django request/response handling, async-to-sync utilities",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="N/A (Django dependency)",
        justification=(
            "ASGI/WSGI compatibility layer used by Django's sync/async "
            "dispatch machinery."
        ),
    ),
    DependencyItem(
        name="django-environ",
        version_spec="==0.14.0",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem="config/settings/* environment and .env parsing",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="python-dotenv, pydantic-settings",
        justification=(
            "Reads typed configuration from the environment and .env files for "
            "the split settings modules."
        ),
    ),
    DependencyItem(
        name="sqlparse",
        version_spec="==0.6.0",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem="Django migration SQL formatting and management output",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="N/A (Django dependency)",
        justification=(
            "SQL tokenizer/formatter required by Django's migration machinery."
        ),
    ),
    DependencyItem(
        name="annotated-types",
        version_spec="==0.8.0",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem="Pydantic model annotations",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="N/A (pydantic dependency)",
        justification="PEP 593 Annotated type utilities consumed by pydantic v2.",
    ),
    DependencyItem(
        name="typing_extensions",
        version_spec="==4.16.0",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem="Type annotations across backend modules",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="N/A (stdlib typing on newer Python)",
        justification=(
            "Backports newer typing constructs used by pydantic/django-stubs."
        ),
    ),
    DependencyItem(
        name="typing-inspection",
        version_spec="==0.4.2",
        ecosystem=Ecosystem.BACKEND_CORE,
        affects_subsystem="Pydantic typing introspection",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="N/A (pydantic dependency)",
        justification=(
            "Typing-introspection helpers used by pydantic's schema machinery."
        ),
    ),
    # ── Backend service / worker ─────────────────────────────────────────────
    DependencyItem(
        name="requests",
        version_spec="==2.33.0",
        ecosystem=Ecosystem.BACKEND_SERVICE,
        affects_subsystem="Outbound Steam API and reCAPTCHA siteverify HTTP calls",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="httpx, urllib.request",
        justification=(
            "HTTP client used by Steam services and reCAPTCHA verification "
            "with connection timeout controls."
        ),
    ),
    DependencyItem(
        name="urllib3",
        version_spec="==2.7.0",
        ecosystem=Ecosystem.BACKEND_SERVICE,
        affects_subsystem="HTTP connection pooling underneath requests",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="N/A (requests dependency)",
        justification=(
            "Low-level HTTP/connection-pooling library underpinning requests."
        ),
    ),
    DependencyItem(
        name="gunicorn",
        version_spec="==23.0.0",
        ecosystem=Ecosystem.BACKEND_SERVICE,
        affects_subsystem="Production WSGI process serving the Django application",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="uWSGI, Daphne",
        justification=(
            "WSGI server process manager running Django in production (Render)."
        ),
    ),
    DependencyItem(
        name="whitenoise",
        version_spec="==6.9.0",
        ecosystem=Ecosystem.BACKEND_SERVICE,
        affects_subsystem="Serving collected Django Admin static assets",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="django-storages + CDN",
        justification=(
            "Serves collected static files (Admin CSS/JS) without a separate "
            "web-server or CDN layer."
        ),
    ),
    # Stdlib recognition (eliminating unnecessary third-party packages)
    DependencyItem(
        name="ipaddress (Python stdlib)",
        version_spec="Built-in (Python 3.12+)",
        ecosystem=Ecosystem.BACKEND_SERVICE,
        affects_subsystem=(
            "security/ip_engine.py — O(log N) integer range conversion and "
            "binary search for VPN CIDRs"
        ),
        lifecycle_status=LifecycleStatus.CORE,
        alternatives="netaddr, py2-ipaddress",
        justification=(
            "Standard library module satisfies all subnet parsing and integer "
            "conversion needs. Avoids third-party supply-chain bloat like "
            "netaddr."
        ),
    ),
    # ── Frontend & BFF architecture ──────────────────────────────────────────
    DependencyItem(
        name="allprofanity",
        version_spec="^2.4.0",
        ecosystem=Ecosystem.FRONTEND_CORE,
        affects_subsystem=(
            "Content moderation — profanity gate for profile bios, display "
            "names, and registration usernames (lib/profanity.ts, BFF validators)"
        ),
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="bad-words, naughty-words, hand-rolled word lists",
        justification=(
            "Evasion-resistant multilingual profanity filter (leet-speak, masked "
            "words, homoglyphs) with zero runtime dependencies, so it runs safely "
            "in both the Astro BFF and the signup client. Custom banned terms "
            "extend it via EXTRA_BANNED_WORDS in lib/profanity.ts."
        ),
    ),
    DependencyItem(
        name="astro",
        version_spec="^7.1.3",
        ecosystem=Ecosystem.FRONTEND_CORE,
        affects_subsystem=(
            "Static site generation, SSR Node BFF (pages/api/auth/*), pre-paint islands"
        ),
        lifecycle_status=LifecycleStatus.CORE,
        alternatives="Next.js, Remix, SvelteKit",
        justification=(
            "Island architecture ships zero client JavaScript by default while "
            "providing native Node SSR for BFF proxy routing."
        ),
    ),
    DependencyItem(
        name="@astrojs/vercel",
        version_spec="^11.0.3",
        ecosystem=Ecosystem.FRONTEND_CORE,
        affects_subsystem=(
            "Vercel adapter for Astro server output (production deployment)"
        ),
        lifecycle_status=LifecycleStatus.CORE,
        alternatives="@astrojs/node, @astrojs/netlify",
        justification=(
            "Enables Astro's on-demand server rendering on the Vercel platform."
        ),
    ),
    DependencyItem(
        name="d3",
        version_spec="^7.9.0",
        ecosystem=Ecosystem.FRONTEND_UI,
        affects_subsystem="Skill radar / visualization primitives",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="N/A (foundation for plot)",
        justification=(
            "Data-Driven Documents — core visualization primitives underlying "
            "Observable Plot and radar rendering."
        ),
    ),
    DependencyItem(
        name="@observablehq/plot",
        version_spec="^0.6.17",
        ecosystem=Ecosystem.FRONTEND_UI,
        affects_subsystem="Skill-profile charts and classification visualizations",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="Chart.js, ECharts",
        justification=(
            "D3-based exploratory visualization library used for skill-profile "
            "charts in the score components."
        ),
    ),
    DependencyItem(
        name="@websr/websr",
        version_spec="^0.0.16",
        ecosystem=Ecosystem.FRONTEND_CORE,
        affects_subsystem="Client-side game-image upscaling (lib/game-image-upscale*)",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="waifu2x (service-side), sharp (server-side)",
        justification=(
            "WebAssembly neural upscaler executed in the browser to enhance "
            "game artwork without server-side image processing."
        ),
    ),
    DependencyItem(
        name="katex",
        version_spec="^0.18.4",
        ecosystem=Ecosystem.FRONTEND_UI,
        affects_subsystem="Mathematical typesetting in methodology pages",
        lifecycle_status=LifecycleStatus.REQUIRED,
        alternatives="MathJax",
        justification=(
            "Renders LaTeX equations in statistical-methodology documentation pages."
        ),
    ),
    DependencyItem(
        name="tailwindcss",
        version_spec="^4.3.3",
        ecosystem=Ecosystem.FRONTEND_UI,
        affects_subsystem=(
            "Utility-first styling, CSS variable design tokens, responsive UI "
            "components"
        ),
        lifecycle_status=LifecycleStatus.CORE,
        alternatives="UnoCSS, StyleX, Sass",
        justification=(
            "Compiles utility classes directly into CSS using the project "
            "design tokens with zero client-side runtime overhead."
        ),
    ),
    DependencyItem(
        name="typescript",
        version_spec="^6.0.3",
        ecosystem=Ecosystem.FRONTEND_CORE,
        affects_subsystem=(
            "Static typing across Astro components, client stores, and BFF API proxies"
        ),
        lifecycle_status=LifecycleStatus.CORE,
        alternatives="JavaScript with JSDoc, Flow",
        justification=(
            "Enforces end-to-end type contracts matching Django Ninja schema payloads."
        ),
    ),
    # ── Tooling & security infrastructure ────────────────────────────────────
    DependencyItem(
        name="django-stubs",
        version_spec="==6.0.2",
        ecosystem=Ecosystem.INFRA_DEVOPS,
        affects_subsystem="Backend static typing (django-stubs + BasedPyright)",
        lifecycle_status=LifecycleStatus.DEV_TOOL,
        alternatives="No typing stubs (untyped Django)",
        justification=(
            "Provides PEP 561 typing stubs over Django APIs for the type checker."
        ),
    ),
    DependencyItem(
        name="django-stubs-ext",
        version_spec="==6.0.2",
        ecosystem=Ecosystem.INFRA_DEVOPS,
        affects_subsystem="Backend static typing extensions",
        lifecycle_status=LifecycleStatus.DEV_TOOL,
        alternatives="N/A (companion to django-stubs)",
        justification="Extended Django typing helpers used alongside django-stubs.",
    ),
    DependencyItem(
        name="vitest",
        version_spec="^4.1.10",
        ecosystem=Ecosystem.INFRA_DEVOPS,
        affects_subsystem="Frontend unit and BFF proxy test suites",
        lifecycle_status=LifecycleStatus.DEV_TOOL,
        alternatives="Jest, Mocha",
        justification=(
            "Executes frontend unit and component tests using the same Vite "
            "build configuration and module resolution as Astro."
        ),
    ),
    DependencyItem(
        name="ruff",
        version_spec="==0.16.0",
        ecosystem=Ecosystem.INFRA_DEVOPS,
        affects_subsystem="Backend linter and formatter",
        lifecycle_status=LifecycleStatus.DEV_TOOL,
        alternatives="Black + Flake8 + isort",
        justification=(
            "Consolidates linting, import sorting, and code formatting into a "
            "single tool, replacing separate flake8, isort, and black "
            "configurations."
        ),
    ),
    DependencyItem(
        name="basedpyright",
        version_spec="==1.32.1",
        ecosystem=Ecosystem.INFRA_DEVOPS,
        affects_subsystem="Strict static type checker across apps/backend/",
        lifecycle_status=LifecycleStatus.DEV_TOOL,
        alternatives="mypy, pyre",
        justification=(
            "Strict static analysis catching type discrepancies and unhandled "
            "nullability with zero runtime penalty."
        ),
    ),
    DependencyItem(
        name="pip-audit",
        version_spec="==2.10.1",
        ecosystem=Ecosystem.INFRA_DEVOPS,
        affects_subsystem="CI automated backend dependency vulnerability scanning",
        lifecycle_status=LifecycleStatus.DEV_TOOL,
        alternatives="Safety, Snyk",
        justification=(
            "Official PyPI-backed vulnerability auditor scanning against the "
            "Python Packaging Advisory Database."
        ),
    ),
    DependencyItem(
        name="smtp4dev (Docker)",
        version_spec="rnwood/smtp4dev:v3",
        ecosystem=Ecosystem.INFRA_DEVOPS,
        affects_subsystem=(
            "Local SMTP mock server (port 2525) & inspection Web UI (port 3000)"
        ),
        lifecycle_status=LifecycleStatus.DEV_TOOL,
        alternatives="Mailpit, MailHog",
        justification=(
            "Lightweight mock SMTP container enabling local end-to-end email "
            "verification testing without external mail accounts."
        ),
    ),
)
