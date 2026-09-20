from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from timeutil import today_str

if TYPE_CHECKING:
    import discord
    from database import DatabaseManager


def _bot_today() -> str:
    """Today's date as ``YYYY-MM-DD`` in the bot's target timezone.

    Daily games (Wordle, ...) tie every score to the day it was posted,
    which is how scores are de-duplicated per user per game.  The day
    boundary follows the bot's ``TIMEZONE`` setting, so a score posted
    just after midnight in that timezone belongs to the new day.
    """
    return today_str()


def message_author_display_name(message: "discord.Message") -> str:
    """Server-nickname-aware display name for a message's author.

    ``discord.Member.display_name`` already prefers the server nickname;
    the gap is when the author resolves to a plain :class:`discord.User`
    — REST-fetched messages (e.g. ``!backfill`` history) don't carry
    member data, so ``message.author`` stays a ``User`` unless the member
    happens to be in the guild cache. In that case the guild cache is
    consulted so server nicknames are still respected.

    Falls back to the global name, then the username, then ``""``.
    """
    author = getattr(message, "author", None)
    if author is None:
        return ""
    # A Member exposes `.nick`; a plain User does not.
    if not hasattr(author, "nick"):
        guild = getattr(message, "guild", None)
        get_member = getattr(guild, "get_member", None)
        if get_member is not None:
            member = get_member(author.id)
            if member is not None:
                author = member
    return (
        getattr(author, "display_name", None)
        or getattr(author, "name", None)
        or ""
    )


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
    day: str = field(default_factory=_bot_today)  # YYYY-MM-DD (bot's timezone)
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
    score: int | float
    meta: dict[str, str] | None = None


class ScoreParser(ABC):
    """Base class for game parsers — one parser per game.

    Subclass this for each game (Wordle, MapTap, ...). Each subclass must:

        - set the ``game`` class attribute to a stable identifier, e.g. "wordle"
        - implement ``can_parse`` / ``parse`` / ``format_response``

    Optionally set ``score_sort`` if lower scores aren't better for this game,
    and ``game_url`` to point players at the game's website (used by the daily
    reminder to list every supported game with a link).

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
    # Link to the game's website, shown in the daily reminder. Leave empty
    # if the game has no public URL.
    game_url: str = ""

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
            user_name=response.username or message_author_display_name(message),
            game=self.game,
            day=response.day,
            score=response.score,
            meta=response.meta,
        )