"""Shared leaderboard rendering.

This module owns ``build_scoreboard_embed`` — the **single** function that
both the ``!scores`` command and the local tester call to turn a list of
:class:`ScoreRecord` rows into a Discord embed.

trivial sends that embed to the channel; the local tester renders the same
embed as terminal text via ``render_embed``.  Two views, one data shape.
"""

from __future__ import annotations

from typing import Callable

import discord

from .base import ScoreRecord

_SortOrders = dict[str, str]  # game -> "asc" | "desc" (default "asc")
_DisplayName = Callable[[ScoreRecord], str]  # record -> name to show/sort by


def _fmt_score(score: int | float) -> str:
    """Render a score for the leaderboard: 50.0 → '50', 40.49 → '40.49'."""
    if isinstance(score, float) and score.is_integer():
        return str(int(score))
    return str(score)


def _ranked(
    records: list[ScoreRecord],
    orders: _SortOrders,
    display_name: _DisplayName | None = None,
) -> list[ScoreRecord]:
    """Sort records honoring each game's direction (lower=better by default).

    *display_name* is an optional ``callable(ScoreRecord) -> str`` returning
    the name to sort/display (e.g. the user's current server nickname);
    it defaults to the stored ``user_name``.
    """
    name = display_name or (lambda r: r.user_name)

    def key(r: ScoreRecord) -> tuple[int, str]:
        score = r.score
        if orders.get(r.game, "asc") == "desc":
            score = -score
        return score, name(r).lower()

    return sorted(records, key=key)


def build_scoreboard_embed(
    records: list[ScoreRecord],
    *,
    game: str | None = None,
    day: str | None = None,
    title: str | None = None,
    color: int = 0x2F3136,
    sort_orders: _SortOrders | None = None,
    guild: discord.Guild | None = None,
) -> discord.Embed:
    """Return a Discord embed representing a game leaderboard.

    When *game* is given only that game's scores appear; otherwise every
    game present in *records* is shown grouped by game name.

    *sort_orders* maps a game identifier to ``"asc"`` (lower is better) or
    ``"desc"`` (higher is better) — build it from registered parsers via
    ``{p.game: p.score_sort for p in parsers}``.

    *guild* is the server the leaderboard is shown in. When given, each
    user's **current server nickname** (via ``guild.get_member``) is used
    instead of the name stored with the score, so leaderboards reflect
    nickname changes (and nicknames set after scoring). Users no longer in
    the server fall back to the stored name.
    """
    orders = sort_orders or {}

    def _display_name(r: ScoreRecord) -> str:
        if guild is not None:
            member = guild.get_member(r.user_id)
            if member is not None:
                return member.display_name
        return r.user_name

    if not records:
        heading = day or "all time"
        label = game.title() if game else "Scores"
        return discord.Embed(
            title=title or f"🏆 {label} — {heading}",
            description="No scores recorded yet.",
            color=color,
        )

    # Date label for the title
    date_label = day or (
        records[0].day if len(set(r.day for r in records)) == 1 else "all time"
    )

    # ── Single-game view ──────────────────────────────────────────────
    if game:
        if not title:
            title = f"🏆 {game.title()} — {date_label}"
        ranked = _ranked(records, orders, _display_name)
        lines = [
            f"**{i}.** {_display_name(r)} — **{_fmt_score(r.score)}**"
            for i, r in enumerate(ranked, 1)
        ]
        embed = discord.Embed(title=title, description="\n".join(lines), color=color)
        embed.set_footer(
            text=f"{len(records)} score{'s' if len(records) != 1 else ''} recorded"
        )
        return embed

    # ── Multi-game view — one field per game ──────────────────────────
    if not title:
        title = f"🏆 Scores — {date_label}"
    embed = discord.Embed(title=title, color=color)

    grouped: dict[str, list[ScoreRecord]] = {}
    for r in records:
        grouped.setdefault(r.game, []).append(r)

    for game_name in sorted(grouped):
        game_records = _ranked(grouped[game_name], orders, _display_name)
        lines = [f"{_display_name(r)} — **{_fmt_score(r.score)}**" for r in game_records]
        embed.add_field(name=game_name.title(), value="\n".join(lines), inline=True)

    embed.set_footer(
        text=f"{len(records)} score{'s' if len(records) != 1 else ''} recorded "
             f"across {len(grouped)} game{'s' if len(grouped) != 1 else ''}"
    )
    return embed