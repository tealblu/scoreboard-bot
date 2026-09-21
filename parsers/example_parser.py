from __future__ import annotations

import discord

from .base import ScoreParser, ScoreResponse, message_author_display_name


class ExampleScoreParser(ScoreParser):
    """Skeleton parser — copy this file to add a REAL game parser."""

    game = "example"
    hidden = True  # skeleton only: keep out of presence/reminder listings
    # game_url = "https://yourgame.example"  # shown in the daily reminder

    def can_parse(self, message: discord.Message) -> bool:
        # TODO: check message.content against this game's expected format
        return False

    def parse(self, message: discord.Message) -> ScoreResponse:
        # TODO: extract the author's score from the message
        return ScoreResponse(
            game=self.game,
            title="Example Scores",
            score=None,  # TODO: e.g. number of guesses
            user_id=message.author.id,
            username=message_author_display_name(message),
            # meta={"number": "1234", "mode": "normal"},
        )

    def format_response(self, score_response: ScoreResponse) -> discord.Embed:
        # TODO: build a rich embed from the parsed data
        embed = discord.Embed(
            title=score_response.title,
            description=score_response.description,
            color=score_response.color,
        )
        return embed