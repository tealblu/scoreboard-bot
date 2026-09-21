from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse, message_author_display_name


class KrillionScoreParser(ScoreParser):
    """Parser for Krillion daily scores."""

    game = "krillion"
    score_sort = "desc"  # higher score is better
    game_url = "https://krillion.io"

    # Matches "Krillion #64" — the puzzle number.
    _header_re = re.compile(r"Krillion\s*#\s*(\d+)", re.IGNORECASE)

    async def can_parse(self, message: discord.Message) -> bool:
        # Require the "Krillion #N" header and a standalone numeric score line.
        if self._header_re.search(message.content) is None:
            return False
        return any(line.strip().isdigit() for line in message.content.splitlines())

    async def parse(self, message: discord.Message) -> ScoreResponse:
        lines = message.content.strip().splitlines()

        header_match = self._header_re.search(message.content)
        number = header_match.group(1) if header_match else ""

        score = None
        for line in lines:
            stripped = line.strip()
            if stripped.isdigit():
                score = int(stripped)
                break

        board_lines = [
            line.strip()
            for line in lines
            if line.strip() and not line.strip().isdigit()
            and not self._header_re.search(line)
        ]

        resp = ScoreResponse(
            title="Krillion",
            score=score,
            game=self.game,
            user_id=message.author.id,
            username=message_author_display_name(message),
        )
        if number:
            resp.meta["number"] = number

        header = f"Krillion #{number}" if number else "Krillion"
        resp.description = "\n".join([header, *board_lines])

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
