"""Shared leaderboard rendering.
"""

from __future__ import annotations

from typing import Callable

import discord

from .base import ScoreRecord
from .common import format_score

_SortOrders = dict[str, str]  # game -> "asc" | "desc" (default "asc")
_DisplayName = Callable[[ScoreRecord], str]  # record -> name to show/sort by


def _ranked(
    records: list[ScoreRecord],
    orders: _SortOrders,
    display_name: _DisplayName | None = None,
) -> list[ScoreRecord]:
    """Sort records honoring each game's direction (lower=better by default)."""
    name = display_name or (lambda r: r.user_name)

    def key(r: ScoreRecord) -> tuple[int | float, str]:
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
    """Return a Discord embed representing a game leaderboard."""
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
            f"**{i}.** {_display_name(r)} — **{format_score(r.score)}**"
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
        lines = [f"{_display_name(r)} — **{format_score(r.score)}**" for r in game_records]
        embed.add_field(name=game_name.title(), value="\n".join(lines), inline=True)

    embed.set_footer(
        text=f"{len(records)} score{'s' if len(records) != 1 else ''} recorded "
             f"across {len(grouped)} game{'s' if len(grouped) != 1 else ''}"
    )
    return embed
