from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse


class CatfishingScoreParser(ScoreParser):
    """Parser for catfishing.net daily scores.

    Expected message format::

        catfishing.net
        #815 - 4/10
        🐈🐟🐟🐟🐈
        🐈🐟🐟🐈🐟

    ``4/10`` is correct guesses out of 10 rounds — the numerator is the
    recorded score (higher is better). The puzzle number (#815) and
    round total are stored in meta; the grid is shown in the embed for
    context. Like other daily games, the score is tied to the day it
    was posted (UTC).
    """

    game = "catfishing"
    score_sort = "desc"  # higher score is better

    # "catfishing.net" — the share URL header.
    _url_re = re.compile(r"catfishing\.net", re.IGNORECASE)
    # "#815 - 4/10" — puzzle number and correct/total score.
    _number_re = re.compile(r"#\s*(\d+)")
    _score_re = re.compile(r"(\d+)\s*/\s*(\d+)")

    async def can_parse(self, message: discord.Message) -> bool:
        # Require the URL AND a "#N - X/Y" score line so a bare mention
        # of the site doesn't match (and can't record a None score).
        if self._url_re.search(message.content) is None:
            return False
        return any(
            self._score_re.search(line)
            for line in message.content.splitlines()
        )

    async def parse(self, message: discord.Message) -> ScoreResponse:
        lines = message.content.strip().splitlines()

        # -- Puzzle number --
        number_match = self._number_re.search(message.content)
        number = number_match.group(1) if number_match else ""

        # -- Score: "X/Y" — record the numerator --
        score = None
        total = None
        for line in lines:
            m = self._score_re.search(line)
            if m:
                score = int(m.group(1))
                total = m.group(2)
                break

        # -- Emoji grid for display --
        grid_lines = [
            line.strip()
            for line in lines
            if line.strip()
            and self._score_re.search(line) is None
            and self._url_re.search(line) is None
        ]

        # -- Build the response --
        resp = ScoreResponse(
            title="Catfishing",
            score=score,
            game=self.game,
            user_id=message.author.id,
            username=message.author.display_name,
        )
        if number:
            resp.meta["number"] = number
        if total:
            resp.meta["total"] = total

        # Show puzzle number + score ratio + emoji grid in the embed.
        header = f"#{number} · {score}/{total}" if number else f"{score}/{total}"
        resp.description = "\n".join([header, *grid_lines])

        return resp

    async def format_response(self, score_response: ScoreResponse) -> discord.Embed:
        embed = discord.Embed(
            title=score_response.title,
            description=score_response.description,
            color=score_response.color,
        )
        embed.add_field(name="Score", value=str(score_response.score), inline=True)
        embed.set_footer(text=f"{score_response.username} · {score_response.day}")
        return embed