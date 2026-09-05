"""
Authentication request/response schemas — SBGC-217 / SBGC-218.

Zero-PII: the only identity attribute ever returned to the client is the
public ``username`` string.  Database IDs, email addresses, staff/superuser
flags, hashes, and timestamps are never part of these contracts.

SBGC-218 adds the pre-registration sign-up schemas (username availability,
email verification challenge, verification status, and final registration).
"""

import re

from api.schemas import ApiRequestSchema
from ninja import Field, Schema
from pydantic import field_validator

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]{4,20}$")
USERNAME_FORMAT_MESSAGE = (
    "Username must be 4-20 alphanumeric characters, underscores, or hyphens."
)


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


# ── SBGC-218 sign-up schemas ────────────────────────────────────────────────


class CheckUsernameRequestSchema(ApiRequestSchema):
    username: str = Field(..., min_length=4, max_length=20)

    @field_validator("username")
    @classmethod
    def validate_username_format(cls, value: str) -> str:
        if not USERNAME_REGEX.match(value):
            raise ValueError(USERNAME_FORMAT_MESSAGE)
        return value


class CheckUsernameResponseSchema(Schema):
    available: bool
    username: str


class VerifyEmailRequestSchema(ApiRequestSchema):
    email: str = Field(..., max_length=254)
    recaptcha_token: str
    company_website: str = ""  # Honeypot field


class VerifyEmailResponseSchema(Schema):
    challenge_id: str
    message: str = "Verification email sent."


class VerificationStatusResponseSchema(Schema):
    verified: bool


class ConfirmEmailRequestSchema(ApiRequestSchema):
    token: str


class ConfirmEmailResponseSchema(Schema):
    success: bool


class SignUpRequestSchema(ApiRequestSchema):
    username: str = Field(..., min_length=4, max_length=20)
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    challenge_id: str
    recaptcha_token: str
    company_website: str = ""  # Honeypot field

    @field_validator("username")
    @classmethod
    def validate_username_format(cls, value: str) -> str:
        if not USERNAME_REGEX.match(value):
            raise ValueError(USERNAME_FORMAT_MESSAGE)
        return value
