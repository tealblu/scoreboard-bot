from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse, message_author_display_name


class CatfishingScoreParser(ScoreParser):
    """Parser for catfishing.net daily scores.

    Expected message format::

        catfishing.net
        #815 - 4/10
        🐈🐟🐟🐟🐈
        🐈🐟🐟🐈🐟

    The share header may also spell the site out (``catfishing dot net``)::

        catfishing dot net
        #819 - 8/10 🎉
        🐈🐈🐈🐈🐈
        🐟🐈🐈🐟🐈

    ``4/10`` is correct guesses out of 10 rounds — the numerator is the
    recorded score (higher is better). The puzzle number (#815) and
    round total are stored in meta; the grid is shown in the embed for
    context. Like other daily games, the score is tied to the day it
    was posted (in the bot's timezone).
    """

    game = "catfishing"
    score_sort = "desc"  # higher score is better
    game_url = "https://catfishing.net"

    # The share header is the first line and always names the game — either
    # "catfishing.net" or "catfishing dot net" — so match the word
    # "catfishing" there instead of the whole URL (the URL suffix varies).
    _header_re = re.compile(r"\bcatfishing\b", re.IGNORECASE)
    # "#815 - 4/10" — puzzle number and correct/total score.
    _number_re = re.compile(r"#\s*(\d+)")
    _score_re = re.compile(r"(\d+)\s*/\s*(\d+)")

    async def can_parse(self, message: discord.Message) -> bool:
        # The share header is the first line: look for the game name there,
        # regardless of how the URL is written ("catfishing.net",
        # "catfishing dot net", ...). Also require a "#N - X/Y" score line,
        # so a bare mention of the game without a score doesn't match (and
        # can't record a None score).
        lines = message.content.strip().splitlines()
        if not lines or self._header_re.search(lines[0]) is None:
            return False
        return any(
            self._score_re.search(line)
            for line in lines
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
            and self._header_re.search(line) is None
        ]

        # -- Build the response --
        resp = ScoreResponse(
            title="Catfishing",
            score=score,
            game=self.game,
            user_id=message.author.id,
            username=message_author_display_name(message),
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