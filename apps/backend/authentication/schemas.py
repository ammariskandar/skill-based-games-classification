"""
Authentication request/response schemas — SBGC-217.

Zero-PII: the only identity attribute ever returned to the client is the
public ``username`` string.  Database IDs, email addresses, staff/superuser
flags, hashes, and timestamps are never part of these contracts.
"""

from api.schemas import ApiRequestSchema
from ninja import Field, Schema


class LoginRequestSchema(ApiRequestSchema):
    username: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Target user handle",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Raw credential string",
    )


class AuthStatusResponseSchema(Schema):
    authenticated: bool
    username: str | None = None
