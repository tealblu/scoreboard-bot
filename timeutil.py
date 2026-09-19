"""Bot-wide timezone handling — the single source of truth for "what day is it".

Every part of trivial that needs today's date, yesterday's date, the current
clock time, or the calendar day a message/share belongs to goes through this
module.  One environment variable — ``TIMEZONE`` — therefore controls:

* which ``YYYY-MM-DD`` a score is stored and read under (``user_scores.day``)
* which calendar day the daily reminder treats as "today"/"yesterday"
  (``daily_reminders.last_fired`` and the reminder loop)
* the timezone the per-guild reminder clock (``daily_reminders.reminder_time``)
  is interpreted in
* the reference year the date parsers (dialed, maptap) resolve "Sep 18"
  against

Set ``TIMEZONE`` to an IANA timezone name, e.g. ``America/New_York`` or
``Asia/Tokyo``.  It defaults to ``UTC`` so existing deployments behave
identically until they opt in.  A bad value fails fast at import time rather
than silently shifting every recorded day.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "UTC"


def _load_timezone() -> ZoneInfo:
    name = os.getenv("TIMEZONE", default=DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Invalid TIMEZONE {name!r} — expected an IANA timezone name "
            "(e.g. 'UTC', 'America/New_York', 'Europe/London'). "
            "See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones."
        ) from exc


TARGET_TZ: ZoneInfo = _load_timezone()


def bot_tz() -> ZoneInfo:
    """The bot's configured timezone (e.g. ``America/New_York``)."""
    return TARGET_TZ


def now() -> datetime:
    """The current moment in the bot's timezone (timezone-aware)."""
    return datetime.now(TARGET_TZ)


def as_bot_tz(value: datetime) -> datetime:
    """Convert *value* to the bot's timezone.

    Naive datetimes are assumed to be UTC — the historical behaviour, and
    what Discord's timestamps are expressed in.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TARGET_TZ)


def today_str() -> str:
    """Today's date as ``YYYY-MM-DD`` in the bot's timezone."""
    return now().strftime("%Y-%m-%d")


def yesterday_str() -> str:
    """Yesterday's date as ``YYYY-MM-DD`` in the bot's timezone."""
    return (now() - timedelta(days=1)).strftime("%Y-%m-%d")


def time_str() -> str:
    """The current clock time as ``HH:MM`` in the bot's timezone."""
    return now().strftime("%H:%M")


def day_string(value: datetime) -> str:
    """The calendar date *value* falls on in the bot's timezone, ``YYYY-MM-DD``."""
    return as_bot_tz(value).strftime("%Y-%m-%d")


def now_label() -> str:
    """Short human-friendly date label, e.g. ``2026-09-19 (America/New_York)``."""
    return f"{today_str()} ({str(TARGET_TZ)})"