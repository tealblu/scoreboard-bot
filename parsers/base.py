from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import discord
    from database import DatabaseManager


def _utc_today() -> str:
    """Today's date as ``YYYY-MM-DD`` (UTC).

    Daily games (Wordle, ...) tie every score to the day it was posted,
    which is how scores are de-duplicated per user per game.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class ScoreResponse:
    """Parsed data for ONE user for ONE game.

    The message model trivial targets is:

        many users x many games — one score per message.

    A message contains a single player's daily result for a single game
    (e.g. ``Wordle 1,234 4/6``). ``score``, ``day`` and ``meta`` are what
    get persisted to the database; ``title``/``description``/``fields``/
    ``footer``/``color`` shape the embed posted to the channel.
    """

    title: str = ""
    score: int | None = None  # The value recorded for the user (e.g. guesses)
    game: str = ""  # Falls back to the parser's `game` if left unset
    user_id: int | None = None  # Discord user ID of the scorer
    username: str = ""  # Display name, for logging / embeds
    day: str = field(default_factory=_utc_today)  # YYYY-MM-DD for this score
    meta: dict[str, str] = field(default_factory=dict)  # e.g. {"number": "1234", "mode": "hard"}
    # Legacy multi-player fallback — most parsers leave this empty.
    scores: dict[str, int] = field(default_factory=dict)
    description: str | None = None
    color: int = 0x2F3136  # Default Discord dark embed color
    fields: list[tuple[str, str, bool]] = field(default_factory=list)
    footer: str | None = None


@dataclass
class ScoreRecord:
    """One row from the ``user_scores`` table — the read-side counterpart to
    :class:`ScoreResponse`.

    Returned by ``DatabaseManager.get_scores`` and consumed by
    :func:`parsers.scoring.build_scoreboard_embed` to render the leaderboard.
    """

    user_id: int
    user_name: str
    game: str
    day: str
    score: int
    meta: dict[str, str] | None = None


class ScoreParser(ABC):
    """Base class for game parsers — one parser per game.

    Subclass this for each game (Wordle, MapTap, ...). Each subclass must:

        - set the ``game`` class attribute to a stable identifier, e.g. "wordle"
        - implement ``can_parse`` / ``parse`` / ``format_response``

    Optionally set ``score_sort`` if lower scores aren't better for this game.

    Scoring persistence is handled by the default ``record_score``
    implementation; override it only for game-specific storage.

    Parse flow (owned by the dispatcher / cog):

        1. ``select_parser`` picks the parser whose ``can_parse`` matches
        2. ``parse`` extracts the user's score into a ``ScoreResponse``
        3. ``record_score`` stores it in the database (one row per
           guild, user, game, day)
        4. ``format_response`` turns the response into a Discord embed
    """

    game: str = ""
    # "asc"  = lower score is better  (fewer guesses; Wordle-style)
    # "desc" = higher score is better (more points; arcade-style)
    score_sort: Literal["asc", "desc"] = "asc"

    @abstractmethod
    async def can_parse(self, message: discord.Message) -> bool:
        """Return True if *message* matches this game's score format."""
        ...

    @abstractmethod
    async def parse(self, message: discord.Message) -> ScoreResponse:
        """Extract the author's score and return a ScoreResponse.

        Include ``user_id``/``username`` when the parser can; otherwise
        ``record_score`` falls back to ``message.author``.
        """
        ...

    @abstractmethod
    async def format_response(self, score_response: ScoreResponse) -> discord.Embed:
        """Turn a *ScoreResponse* into a Discord embed ready to send."""
        ...

    async def record_score(
        self,
        message: discord.Message,
        response: ScoreResponse,
        database: DatabaseManager,
    ) -> None:
        """Persist ONE score for THIS game, tied to the message author.

        One row per (guild, user, game, day): re-posting a daily score
        for the same day overwrites the previous value.

        Subclasses may override this for game-specific storage (e.g.
        keeping streaks or extra statistics).
        """
        if not self.game:
            raise ValueError(
                f"{type(self).__name__} must define a `game` identifier "
                "(e.g. 'wordle') so scores can be stored per game."
            )
        await database.record_user_score(
            guild_id=message.guild.id if message.guild else 0,
            user_id=response.user_id or message.author.id,
            user_name=response.username or message.author.display_name,
            game=self.game,
            day=response.day,
            score=response.score,
            meta=response.meta,
        )