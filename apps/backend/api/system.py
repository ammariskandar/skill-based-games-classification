"""
API system/router-level operations — SBGC-38.

Exposes the API root (GET /) with product name and version.
"""

from ninja import Router

from api.errors import STANDARD_ERROR_RESPONSES
from api.schemas import ApiRootResponse

router = Router(tags=["System"])


@router.get(
    "",
    response={200: ApiRootResponse, **STANDARD_ERROR_RESPONSES},
    operation_id="api_root",
    summary="API root",
    description="Returns the API product name and version.",
    url_name="api-root",
)
def api_root(request):
    return ApiRootResponse(name="MyGameDNA API", version="1.0.0")
