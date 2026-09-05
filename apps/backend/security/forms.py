"""Hardened Django Admin login form — SBGC-106."""

from __future__ import annotations

from typing import cast

from authentication.tokens import verify_recaptcha
from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.models import User

from security.models_cache import (
    create_vpn_challenge,
    get_challenge,
    should_challenge_login,
    sign_review_token,
)
from security.notifications import notify_superusers_of_vpn_login


class HardenedAdminAuthenticationForm(AdminAuthenticationForm):
    recaptcha_token = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean(self) -> dict:
        """Verify the reCAPTCHA v3 score before attempting authentication.

        The score gate runs first so a bot never reaches ``authenticate()``
        (and therefore never triggers a VPN challenge or superuser alert).
        """
        token = self.cleaned_data.get("recaptcha_token", "")
        remote_ip = self.request.META.get("REMOTE_ADDR") if self.request else None
        if not verify_recaptcha(token, remote_ip=remote_ip):
            raise forms.ValidationError(
                "Automated bot activity suspected. Access denied."
            )
        return super().clean()

    def confirm_login_allowed(self, user) -> None:
        """Open the VPN/datacenter gate after a successful credential check."""
        super().confirm_login_allowed(user)
        if self.request is None:
            return
        concrete_user = cast(User, user)
        remote_ip = self.request.META.get("REMOTE_ADDR")
        if not remote_ip or not should_challenge_login(concrete_user, remote_ip):
            return

        challenge_id = create_vpn_challenge(
            concrete_user,
            remote_ip,
            self.request.META.get("HTTP_USER_AGENT", ""),
        )
        self.request.session["admin_vpn_challenge_id"] = challenge_id

        challenge = get_challenge(challenge_id)
        if challenge is not None:
            notify_superusers_of_vpn_login(
                self.request,
                concrete_user,
                challenge,
                sign_review_token(challenge_id),
            )
