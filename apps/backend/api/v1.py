"""
v1 API composition — SBGC-38.

Creates the single NinjaAPI instance for version 1, registers routers,
and attaches standard exception handlers.
"""

from classifications.api import router as classifications_router
from django.conf import settings
from games.api import router as games_router
from games.rankings_api import router as rankings_router
from ninja import NinjaAPI

from api.errors import register_handlers
from api.system import router as system_router

docs_url = "/docs" if getattr(settings, "NINJA_API_DOCS_ENABLED", False) else None

api = NinjaAPI(
    title="MyGameDNA API",
    version="1.0.0",
    urls_namespace="api-v1",
    description=(
        "Public API for the MyGameDNA skill-based games classification platform. "
        "Exposes game identities, Challenge and Reward classification profiles, "
        "search, rankings, and catalogue data."
    ),
    openapi_url="/openapi.json",
    docs_url=docs_url,
)

# Attach standard exception handlers.
register_handlers(api)

# Mount domain routers — canonical trailing slashes.
api.add_router("", system_router)
api.add_router("/games/", games_router)
api.add_router("/classifications/", classifications_router)
api.add_router("/rankings/", rankings_router)
