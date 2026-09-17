"""Message → parser dispatch.

The dispatcher owns the question "which parser handles this message?"
It is used by the scoreboard cog and by the local tester so both follow the
exact same decision logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import ScoreParser

if TYPE_CHECKING:
    import discord

logger = logging.getLogger("trivial")


async def select_parser(
    parsers: list[ScoreParser],
    message: discord.Message,
) -> ScoreParser | None:
    """Return the parser that should handle *message*, or None.

    Parsers are tested in registration order; the first one whose
    ``can_parse`` returns ``True`` wins. A parser that raises during
    ``can_parse`` is logged and skipped so one broken parser can't
    block the others.
    """
    for parser in parsers:
        try:
            if await parser.can_parse(message):
                return parser
        except Exception:
            logger.exception(
                "Parser %s failed during can_parse on message %s",
                type(parser).__name__,
                getattr(message, "id", "?"),
            )
    return None