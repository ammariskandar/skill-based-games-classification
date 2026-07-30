"""
Games API router — SBGC-38.

Router ownership boundary for game-domain API operations.
No operations exist yet — models will be implemented in SBGC-4.
"""

from ninja import Router

router = Router(tags=["Games"])
