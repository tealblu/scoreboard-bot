"""Shared leaderboard rendering."""

from __future__ import annotations

from functools import partial
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


# Emoji used by the embed builders.
_TROPHY = "🏆"
_CROWN = "👑"


def _display_name(r: ScoreRecord, guild: discord.Guild | None) -> str:
    """Prefer the member's server nickname; fall back to the stored name."""
    if guild is not None:
        member = guild.get_member(r.user_id)
        if member is not None:
            return member.display_name
    return r.user_name


def _group_by_game(records: list[ScoreRecord]) -> dict[str, list[ScoreRecord]]:
    """Bucket records by game, preserving input order within each bucket."""
    grouped: dict[str, list[ScoreRecord]] = {}
    for record in records:
        grouped.setdefault(record.game, []).append(record)
    return grouped


def _empty_embed(title: str, color: int) -> discord.Embed:
    """Embed to show when no scores have been recorded."""
    return discord.Embed(title=title, description="No scores recorded yet.", color=color)


def _best_per_player(
    records: list[ScoreRecord],
    orders: _SortOrders,
) -> list[ScoreRecord]:
    """Keep each player's single best score (one row per user)."""
    best: dict[int, ScoreRecord] = {}
    for record in records:
        previous = best.get(record.user_id)
        if previous is None:
            best[record.user_id] = record
            continue
        score = record.score
        better = (
            score > previous.score
            if orders.get(record.game, "asc") == "desc"
            else score < previous.score
        )
        if better:
            best[record.user_id] = record
    return list(best.values())


def _average_per_player(records: list[ScoreRecord]) -> list[ScoreRecord]:
    """One row per player holding their mean score, rounded to 2 decimals."""
    totals: dict[int, float] = {}
    counts: dict[int, int] = {}
    first: dict[int, ScoreRecord] = {}
    for record in records:
        user_id = record.user_id
        totals[user_id] = totals.get(user_id, 0.0) + record.score
        counts[user_id] = counts.get(user_id, 0) + 1
        first.setdefault(user_id, record)

    averaged: list[ScoreRecord] = []
    for user_id, total in totals.items():
        template = first[user_id]
        averaged.append(
            ScoreRecord(
                user_id=user_id,
                user_name=template.user_name,
                game=template.game,
                day=template.day,
                score=round(total / counts[user_id], 2),
                meta=template.meta,
            )
        )
    return averaged


def _count_per_player(records: list[ScoreRecord]) -> list[ScoreRecord]:
    """One row per player holding how many scores they recorded."""
    counts: dict[int, int] = {}
    first: dict[int, ScoreRecord] = {}
    for record in records:
        counts[record.user_id] = counts.get(record.user_id, 0) + 1
        first.setdefault(record.user_id, record)

    return [
        ScoreRecord(
            user_id=user_id,
            user_name=first[user_id].user_name,
            game=first[user_id].game,
            day=first[user_id].day,
            score=count,
            meta=first[user_id].meta,
        )
        for user_id, count in counts.items()
    ]


def _wins_per_player(
    records: list[ScoreRecord],
    orders: _SortOrders,
) -> list[ScoreRecord]:
    """One row per player holding how many days they finished first."""
    best_per_day: dict[str, float] = {}
    for record in records:
        score = record.score
        best = best_per_day.get(record.day)
        if best is None or (
            score > best
            if orders.get(record.game, "asc") == "desc"
            else score < best
        ):
            best_per_day[record.day] = score

    wins: dict[int, int] = {}
    first: dict[int, ScoreRecord] = {}
    for record in records:
        if record.score == best_per_day[record.day]:
            wins[record.user_id] = wins.get(record.user_id, 0) + 1
        first.setdefault(record.user_id, record)

    return [
        ScoreRecord(
            user_id=user_id,
            user_name=first[user_id].user_name,
            game=first[user_id].game,
            day=first[user_id].day,
            score=wins[user_id],
            meta=first[user_id].meta,
        )
        for user_id in wins
    ]


def _aggregate_per_player(
    records: list[ScoreRecord],
    orders: _SortOrders,
    metric: str,
) -> list[ScoreRecord]:
    """Reduce each player to one row per the chosen *metric*."""
    if metric == "top":
        return _best_per_player(records, orders)
    if metric == "wins":
        return _wins_per_player(records, orders)
    if metric == "count":
        return _count_per_player(records)
    return _average_per_player(records)


# — Leaderboard metrics: canonical keys, user-facing aliases, labels and
# ranking rules. This is the single source of truth shared by the
# /leaderboard command (cogs/scoreboard.py), this embed builder and
# local_tester.py, so aliases, validation and labels can never drift apart.

DEFAULT_METRIC = "average"

METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "average": ("average", "avg", "mean"),
    "top": ("top", "best", "max"),
    "wins": ("wins", "win", "victories", "victory"),
    "count": ("count", "plays", "games", "attempts"),
}

METRIC_LABELS: dict[str, str] = {
    "average": "Average score per player",
    "top": "Best score per player",
    "wins": "Wins per player",
    "count": "Plays per player",
}

# Metrics that are always "more is better", regardless of the game's own
# ascending/descending score direction.
ALWAYS_DESC_METRICS = ("wins", "count")


def resolve_metric(metric: str | None) -> str | None:
    """Normalize a user-supplied metric keyword to its canonical key."""
    if metric is None:
        return DEFAULT_METRIC
    key = metric.strip().lower()
    for canonical, aliases in METRIC_ALIASES.items():
        if key in aliases:
            return canonical
    return None


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
    name = partial(_display_name, guild=guild)

    if not records:
        heading = day or "all time"
        label = game.title() if game else "Scores"
        return _empty_embed(title or f"{_TROPHY} {label} — {heading}", color)

    date_label = day or (
        records[0].day if len(set(r.day for r in records)) == 1 else "all time"
    )

    # Single-game view
    if game:
        if not title:
            title = f"{_TROPHY} {game.title()} — {date_label}"
        ranked = _ranked(records, orders, name)
        lines = [
            f"**{i}.** {name(r)} — **{format_score(r.score)}**"
            for i, r in enumerate(ranked, 1)
        ]
        embed = discord.Embed(title=title, description="\n".join(lines), color=color)
        embed.set_footer(
            text=f"{len(records)} score{'s' if len(records) != 1 else ''} recorded"
        )
        return embed

    # Multi-game view: one field per game
    if not title:
        title = f"{_TROPHY} Scores — {date_label}"
    embed = discord.Embed(title=title, color=color)

    grouped = _group_by_game(records)
    for game_name in sorted(grouped):
        game_records = _ranked(grouped[game_name], orders, name)
        lines = [f"{name(r)} — **{format_score(r.score)}**" for r in game_records]
        embed.add_field(name=game_name.title(), value="\n".join(lines), inline=True)

    embed.set_footer(
        text=f"{len(records)} score{'s' if len(records) != 1 else ''} recorded "
             f"across {len(grouped)} game{'s' if len(grouped) != 1 else ''}"
    )
    return embed


def build_leaderboard_embed(
    records: list[ScoreRecord],
    *,
    game: str | None = None,
    day: str | None = None,
    end_day: str | None = None,
    title: str | None = None,
    color: int = 0x2F3136,
    sort_orders: _SortOrders | None = None,
    guild: discord.Guild | None = None,
    metric: str = DEFAULT_METRIC,
) -> discord.Embed:
    """Return an embed showing the top 3 players for each game."""
    if metric not in METRIC_LABELS:
        raise ValueError(f"Unknown leaderboard metric: {metric!r}")
    orders = sort_orders or {}
    if metric in ALWAYS_DESC_METRICS:
        # Wins and plays are "more is better" for every game.
        rank_orders = dict.fromkeys(orders, "desc")
    else:
        rank_orders = orders
    name = partial(_display_name, guild=guild)

    if day and end_day:
        window_label = f"{day} – {end_day}"
    elif day or end_day:
        window_label = day or end_day
    else:
        window_label = "all time"

    label = game.title() if game else "Leaderboard"
    title = title or f"{_CROWN} {label} — {window_label}"

    if not records:
        return _empty_embed(title, color)

    embed = discord.Embed(title=title, color=color)
    grouped = _group_by_game(records)

    for game_name in sorted(grouped):
        aggregated = _aggregate_per_player(grouped[game_name], orders, metric)
        top = _ranked(aggregated, rank_orders, name)[:3]
        lines = [
            f"{_CROWN} **{name(r)}** — **{format_score(r.score)}**"
            if i == 1
            else f"{i}. **{name(r)}** — **{format_score(r.score)}**"
            for i, r in enumerate(top, 1)
        ]
        embed.add_field(name=game_name.title(), value="\n".join(lines), inline=True)

    embed.set_footer(
        text=f"{METRIC_LABELS[metric]} · top 3 per game · {window_label}"
    )
    return embed
