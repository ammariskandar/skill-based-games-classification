"""Daily login buffering — SBGC-186.

Login activity is buffered in Django cache in real time so that repeated
authentications within the same calendar day never issue a synchronous write
to ``UserSecurityProfile``.  The nightly management command
``process_daily_logins_and_superuser_rotation`` flushes the buffer.

Concurrency note: the per-user ``cache.add`` dedup guard is atomic (a user is
counted once per day regardless of burst).  The shared day buffer is a plain
list read-modify-write; a rare lost append under simultaneous first-logins of
*different* users is an accepted tradeoff for a soft login-count metric (the
rate-limit counters in SBGC-107, by contrast, use atomic scalar buckets because
their correctness matters).  The nightly flush is tolerant of that.
"""

from __future__ import annotations

from datetime import date

from django.core.cache import cache

LOGIN_BUFFER_KEY = "login_buffer:{date_str}"
USER_SEEN_KEY = "login_seen:{user_id}:{date_str}"


def record_user_login_activity(user_id: int) -> None:
    """Buffer a distinct daily login for *user_id* without touching the DB."""
    today_str = date.today().isoformat()
    seen_key = USER_SEEN_KEY.format(user_id=user_id, date_str=today_str)

    # Atomic dedup: only the first login of the day for this user proceeds.
    if cache.add(seen_key, True, timeout=86400 * 2):
        buffer_key = LOGIN_BUFFER_KEY.format(date_str=today_str)
        user_ids = cache.get(buffer_key, [])
        user_ids.append(user_id)
        cache.set(buffer_key, user_ids, timeout=86400 * 2)
