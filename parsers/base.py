from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord


@dataclass
class ScoreResponse:
    """Holds the parsed score data and the formatted Discord message."""

    title: str
    scores: dict[str, int] = field(default_factory=dict)
    description: str | None = None
    color: int = 0x2F3136  # Default Discord dark embed color
    fields: list[tuple[str, str, bool]] = field(default_factory=list)
    footer: str | None = None


class ScoreParser(ABC):
    """Base class for all score parsers.

    Subclass this to add support for parsing a new game's score format.
    Each subclass must implement:

        - can_parse(message)  — return True if this parser handles the message
        - parse(message)      — extract scores and return a ScoreResponse
        - format_response(score_response)  — convert the data to a Discord embed

    Register parsers via ``ScoreboardCog.add_parser()`` or by importing
    them in ``cogs/scoreboard.py``.
    """

    @abstractmethod
    async def can_parse(self, message: discord.Message) -> bool:
        """Return True if *message* matches this parser's expected format."""
        ...

    @abstractmethod
    async def parse(self, message: discord.Message) -> ScoreResponse:
        """Parse *message* and return structured score data."""
        ...

    @abstractmethod
    async def format_response(self, score_response: ScoreResponse) -> discord.Embed:
        """Turn a *ScoreResponse* into a Discord embed ready to send."""
        ...
