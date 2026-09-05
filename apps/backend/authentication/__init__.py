"""Authentication application package — SBGC-217.

Session-backed Django authentication exposed through a Django Ninja router
and proxied to the browser by the Astro BFF.  No models or migrations —
session authority lives in ``django.contrib.sessions`` and ``auth_user``.
"""
