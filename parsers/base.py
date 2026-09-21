from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import discord

from timeutil import today_str

if TYPE_CHECKING:
    from database import DatabaseManager


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
    # Hidden parsers are discovered but excluded from user-facing listings
    # (e.g. the rotating presence and the daily reminder).
    hidden: bool = False

    @abstractmethod
    def can_parse(self, message: discord.Message) -> bool:
        """Return True if the message matches this game's score format."""
        ...

    @abstractmethod
    def parse(self, message: discord.Message) -> ScoreResponse:
        """Extract the author's score and return a ScoreResponse."""
        ...

    @abstractmethod
    def format_response(self, score_response: ScoreResponse) -> discord.Embed:
        """Turn the score response into a Discord embed ready to send."""
        ...

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
