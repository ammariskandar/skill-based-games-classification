"""
Architectural tech stack & dependency registry — SBGC-108.

An in-memory catalog of the runtime/CI dependencies, their affected
subsystems, lifecycle status, alternatives, and design justifications.  It is
intentionally *not* a vulnerability database: dynamic CVE state belongs to the
CI audit gates (``pip-audit`` / ``npm audit``), never to a static registry
that would go stale the moment it is written.

Lifecycle status reflects architectural intent (Core / Required / Dev tool /
Under evaluation / Deprecated), not "0 CVEs" claims.
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
    # Backend Core & API
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
            "dependencies."
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
            "High-performance type-safe routing with native Pydantic schema "
            "validation; outpaces DRF in serialization throughput."
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
            "Standard validation engine with compiled Rust core, directly "
            "integrated into Django Ninja."
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
    # Stdlib Recognition (Eliminating Unnecessary Third-Party Packages)
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
    # Frontend & BFF Architecture
    DependencyItem(
        name="astro",
        version_spec=">=5.0.0",
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
        name="tailwindcss",
        version_spec=">=4.0.0",
        ecosystem=Ecosystem.FRONTEND_UI,
        affects_subsystem=(
            "Utility-first styling, CSS variable design tokens, responsive UI "
            "components"
        ),
        lifecycle_status=LifecycleStatus.CORE,
        alternatives="UnoCSS, StyleX, Sass",
        justification=(
            "Engine with native cascade layer support and zero-runtime CSS "
            "bundle output."
        ),
    ),
    DependencyItem(
        name="typescript",
        version_spec=">=5.0.0",
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
    DependencyItem(
        name="vitest",
        version_spec=">=2.0.0",
        ecosystem=Ecosystem.INFRA_DEVOPS,
        affects_subsystem="Frontend unit and BFF proxy test suites",
        lifecycle_status=LifecycleStatus.DEV_TOOL,
        alternatives="Jest, Mocha",
        justification=(
            "Vite-native test runner executing ESM tests rapidly with "
            "out-of-the-box TypeScript support."
        ),
    ),
    # Tooling & Security Infrastructure
    DependencyItem(
        name="ruff",
        version_spec=">=0.6.0",
        ecosystem=Ecosystem.INFRA_DEVOPS,
        affects_subsystem=(
            "Backend linter and code formatter enforcing PEP 8 and flake8-bugbear rules"
        ),
        lifecycle_status=LifecycleStatus.DEV_TOOL,
        alternatives="Black + Flake8 + isort",
        justification=(
            "Single Rust binary executing all backend linting and formatting "
            "in milliseconds."
        ),
    ),
    DependencyItem(
        name="basedpyright",
        version_spec=">=1.19.0",
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
        version_spec=">=2.7.0",
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
