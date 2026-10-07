from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, Literal

import discord

from timeutil import today_str

from .common import format_score

if TYPE_CHECKING:
    from database import DatabaseManager

# A daily reset time in UTC, 24-hour "HH:MM" (single-digit hours accepted,
# e.g. "9:30").
RESET_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def message_author_display_name(message: discord.Message) -> str:
    """Return the author's display name, preferring the server nickname."""
    author = message.author
    # A Member exposes the per-server nickname; a plain User does not, so
    # fall back to the cached member to pick up nicknames like production does.
    if not isinstance(author, discord.Member) and message.guild is not None:
        member = message.guild.get_member(author.id)
        if member is not None:
            author = member
    return author.display_name or author.name


@dataclass
class ScoreResponse:
    """Parsed data for one user for one game."""

    title: str = ""
    score: int | None = None  # The value recorded for the user (e.g. guesses)
    game: str = ""  # Falls back to the parser's `game` if left unset
    user_id: int | None = None  # Discord user ID of the scorer
    username: str = ""  # Display name, for logging / embeds
    day: str = field(default_factory=today_str)  # YYYY-MM-DD (bot's timezone)
    meta: dict[str, str] = field(default_factory=dict)  # e.g. {"number": "1234", "mode": "hard"}
    description: str | None = None
    color: int = 0x2F3136  # Default Discord dark embed color


@dataclass
class ScoreRecord:
    """One row from the ``user_scores`` table used to render leaderboards."""

    user_id: int
    user_name: str
    game: str
    day: str
    score: int | float
    meta: dict[str, str] | None = None


class ScoreParser(ABC):
    """Base class for game parsers — one parser per game."""

    game: str = ""
    # "asc" = lower is better (fewer guesses); "desc" = higher is better (more points).
    score_sort: Literal["asc", "desc"] = "asc"
    # Link to the game's website, shown in the daily reminder.
    game_url: str = ""
    # REQUIRED on every concrete parser: the time in UTC when the game
    # officially resets and moves to the next day, as "HH:MM" (e.g.
    # "04:00" for midnight US Eastern). Scores posted before the reset
    # belong to the previous game day.
    reset_time_utc: str = ""
    # Hidden parsers are discovered but excluded from user-facing listings
    # (e.g. the rotating presence and the daily reminder).
    hidden: bool = False

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Reject concrete parsers that don't declare a reset time."""
        super().__init_subclass__(**kwargs)
        # Concrete parsers set a `game`; helper/abstract bases don't, so
        # they inherit the empty default without complaint.
        if not getattr(cls, "game", ""):
            return
        reset = getattr(cls, "reset_time_utc", "")
        if not isinstance(reset, str) or RESET_TIME_RE.match(reset) is None:
            raise ValueError(
                f"{cls.__name__} must set reset_time_utc to the game's daily "
                f"reset time in UTC as 'HH:MM' (e.g. '00:00'), got {reset!r}."
            )

    def reset_time(self) -> time:
        """This game's daily reset moment as a UTC clock time."""
        hour, _, minute = self.reset_time_utc.partition(":")
        return time(int(hour), int(minute))

    def game_day(self, at: datetime | None = None) -> str:
        """The game day (``YYYY-MM-DD``) in effect at *at* — default: now.

        The day rolls over at ``reset_time_utc``, not at midnight UTC, so
        any moment before the reset still belongs to the previous day.
        Naive datetimes are treated as UTC.
        """
        moment = at if at is not None else datetime.now(timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        moment = moment.astimezone(timezone.utc)
        if moment.time() < self.reset_time():
            moment -= timedelta(days=1)
        return moment.strftime("%Y-%m-%d")

    @abstractmethod
    def can_parse(self, message: discord.Message) -> bool:
        """Return True if the message matches this game's score format."""
        ...

    @abstractmethod
    def parse(self, message: discord.Message) -> ScoreResponse:
        """Extract the author's score and return a ScoreResponse."""
        ...

    def _build_response(
        self,
        message: discord.Message,
        *,
        title: str,
        score: int | float | None,
        day: str | None = None,
    ) -> ScoreResponse:
        """Build a ScoreResponse pre-filled with this game and the author's details.

        :param message: The message the score was extracted from.
        :param title: Title shown on the response embed, e.g. "Color Daily".
        :param score: The numeric score for this game/author/day.
        :param day: Optional ``YYYY-MM-DD`` date; ``None`` resolves the
            game's current day from ``reset_time_utc`` (see :meth:`game_day`).
        """
        resp = ScoreResponse(
            title=title,
            score=score,
            game=self.game,
            user_id=message.author.id,
            username=message_author_display_name(message),
            day=day or self.game_day(),
        )
        return resp

    def format_response(self, score_response: ScoreResponse) -> discord.Embed:
        """Default embed: title, description, a Score field, and author/day footer.

        Override for a richer per-game embed (e.g. extra fields from ``meta``).
        """
        embed = discord.Embed(
            title=score_response.title,
            description=score_response.description,
            color=score_response.color,
        )
        embed.add_field(
            name="Score", value=format_score(score_response.score), inline=True
        )
        embed.set_footer(text=f"{score_response.username} · {score_response.day}")
        return embed

    async def record_score(
        self,
        message: discord.Message,
        response: ScoreResponse,
        database: DatabaseManager,
    ) -> None:
        """Persist ONE score for this game, tied to the message author."""
        if not self.game:
            raise ValueError(
                f"{type(self).__name__} must define a `game` identifier "
                "(e.g. 'wordle') so scores can be stored per game."
            )
        await database.record_user_score(
            guild_id=message.guild.id if message.guild else 0,
            user_id=response.user_id or message.author.id,
            user_name=response.username or message_author_display_name(message),
            game=self.game,
            day=response.day,
            score=response.score,
            meta=response.meta,
        )
