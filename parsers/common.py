"""Small helpers shared by parser implementations."""

from __future__ import annotations

from datetime import datetime

from timeutil import now as bot_now

# Full month names and three-letter abbreviations, both lowercased.
_MONTHS: dict[str, int] = {
    name.lower(): idx
    for idx, name in enumerate(
        [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ],
        start=1,
    )
}
_MONTHS.update(
    {
        name.lower(): idx
        for idx, name in enumerate(
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
            start=1,
        )
    }
)


def format_score(score: int | float | None) -> str:
    """Render a score compactly: ``50.0`` -> ``'50'``, ``40.49`` -> ``'40.49'``."""
    if score is None:
        return "—"
    if isinstance(score, float) and score.is_integer():
        return str(int(score))
    return str(score)


def parse_month_day(month_name: str, day: int) -> str | None:
    """Resolve a month name/abbreviation and day to ``YYYY-MM-DD``.

    A date that would fall in the future is assumed to be from the previous
    year, matching how these games label their daily shares.
    """
    month = _MONTHS.get(month_name.lower().rstrip("."))
    if month is None:
        return None

    now = bot_now()
    try:
        date = datetime(now.year, month, day)
    except ValueError:
        return None

    if date.date() > now.date():
        date = date.replace(year=now.year - 1)
    return date.strftime("%Y-%m-%d")
