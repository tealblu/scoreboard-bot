from __future__ import annotations

import discord

from .base import ScoreParser, ScoreResponse, message_author_display_name


class ExampleScoreParser(ScoreParser):
    """Skeleton parser — copy this file to add a REAL game parser.

    One parser per game: Wordle gets a parser, MapTap gets a parser, etc.
    Set ``game`` to the game's stable identifier (used as the database key)
    and replace the TODO logic below.
    """

    game = "example"
    # game_url = "https://yourgame.example"  # shown in the daily reminder

    async def can_parse(self, message: discord.Message) -> bool:
        # TODO: check message.content against this game's expected format
        return False

    async def parse(self, message: discord.Message) -> ScoreResponse:
        # TODO: extract the author's score from the message
        return ScoreResponse(
            game=self.game,
            title="Example Scores",
            score=None,  # TODO: e.g. number of guesses
            user_id=message.author.id,
            username=message_author_display_name(message),
            # meta={"number": "1234", "mode": "normal"},
        )

    async def format_response(self, score_response: ScoreResponse) -> discord.Embed:
        # TODO: build a rich embed from the parsed data
        embed = discord.Embed(
            title=score_response.title,
            description=score_response.description,
            color=score_response.color,
        )
        if score_response.scores:
            for player, score in score_response.scores.items():
                embed.add_field(name=player, value=str(score), inline=True)
        return embed