from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse, message_author_display_name
from .common import parse_month_day


class MapTapScoreParser(ScoreParser):
    """Parser for www.maptap.gg daily scores.
        www.maptap.gg September 17
        93🏆 99🎯 98🎯 87🎓 62😐
        Final score: 835
    """

    game = "maptap"
    score_sort = "desc"  # higher score is better
    game_url = "https://www.maptap.gg"

    # Match individual round results like "93🏆" or "87🎓".
    _round_re = re.compile(r"(\d+)\s*([^\s\d]+)")

    async def can_parse(self, message: discord.Message) -> bool:
        # Require the URL AND a "Final score:" line so casual mentions of
        # the site (without an actual score) don't match this parser.
        return (
            "www.maptap.gg" in message.content
            and re.search(r"Final score:\s*\d+", message.content, re.IGNORECASE) is not None
        )

    async def parse(self, message: discord.Message) -> ScoreResponse:
        lines = message.content.strip().splitlines()

        score = None
        for line in reversed(lines):
            m = re.search(r"Final score:\s*(\d+)", line, re.IGNORECASE)
            if m:
                score = int(m.group(1))
                break

        day = None
        if lines:
            first = lines[0].strip()
            first = re.sub(r"www\.maptap\.gg\s*", "", first).strip().rstrip(".")
            parts = first.split()
            if len(parts) == 2:
                try:
                    day = parse_month_day(parts[0], int(parts[1]))
                except ValueError:
                    day = None

        rounds: list[str] = []
        for line in lines:
            for match in self._round_re.finditer(line):
                rounds.append(f"{match.group(1)}{match.group(2)}")

        resp = ScoreResponse(
            title="MapTap",
            score=score,
            game=self.game,
            user_id=message.author.id,
            username=message_author_display_name(message),
        )

        if day:
            resp.day = day

        if rounds:
            resp.description = " ".join(rounds)

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
