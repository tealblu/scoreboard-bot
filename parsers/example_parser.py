from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ScoreParser, ScoreResponse

if TYPE_CHECKING:
    import discord


class ExampleScoreParser(ScoreParser):
    """Skeleton parser — replace the logic below with real parsing code.

    This shows the contract that every ScoreParser subclass must satisfy.
    """

    async def can_parse(self, message: discord.Message) -> bool:
        # TODO: check message content against the expected format
        return False

    async def parse(self, message: discord.Message) -> ScoreResponse:
        # TODO: extract player names and scores from the message
        return ScoreResponse(
            title="Example Scores",
            scores={},
        )

    async def format_response(self, score_response: ScoreResponse) -> discord.Embed:
        # TODO: build a rich embed from the parsed data
        embed = discord.Embed(
            title=score_response.title,
            color=score_response.color,
        )
        for player, score in score_response.scores.items():
            embed.add_field(name=player, value=str(score), inline=True)
        return embed
