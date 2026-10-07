from __future__ import annotations

import discord

from .base import ScoreParser, ScoreResponse


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
        return self._build_response(
            message,
            title="Example Scores",
            score=None,  # TODO: e.g. number of guesses
            # meta={"number": "1234", "mode": "normal"},
        )