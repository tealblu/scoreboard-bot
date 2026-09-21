from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse, message_author_display_name


class CatfishingScoreParser(ScoreParser):
    """Parser for catfishing.net daily scores."""

    game = "catfishing"
    score_sort = "desc"  # higher score is better
    game_url = "https://catfishing.net"

    # The share header is its own whole line: "catfishing.net" or "catfishing dot net".
    _header_re = re.compile(
        r"\s*catfishing(?:\s*dot\s*net|\.net)?\s*$", re.IGNORECASE
    )
    # "#815 - 4/10" — puzzle number and correct/total score.
    _number_re = re.compile(r"#\s*(\d+)")
    _score_re = re.compile(r"(\d+)\s*/\s*(\d+)")
    # "X/10" — correct guesses out of 10 rounds; requiring the total filters dates.
    _total = "10"

    async def can_parse(self, message: discord.Message) -> bool:
        # The header line must be followed by an "X/10" score line.
        lines = message.content.strip().splitlines()
        header_index = next(
            (i for i, line in enumerate(lines) if self._header_re.match(line)),
            None,
        )
        if header_index is None:
            return False
        for line in lines[header_index + 1 :]:
            m = self._score_re.search(line)
            if m is not None and m.group(2) == self._total:
                return True
        return False

    async def parse(self, message: discord.Message) -> ScoreResponse:
        lines = message.content.strip().splitlines()

        # Lines before the share header are preamble and are ignored.
        header_index = next(
            (i for i, line in enumerate(lines) if self._header_re.match(line)),
            None,
        )
        share_lines = lines[header_index + 1 :] if header_index is not None else lines

        # -- Puzzle number from the share lines --
        number = ""
        for line in share_lines:
            m = self._number_re.search(line)
            if m:
                number = m.group(1)
                break

        # -- Score: the "X/10" line, recording the numerator --
        score = None
        total = None
        for line in share_lines:
            m = self._score_re.search(line)
            if m is not None and m.group(2) == self._total:
                score = int(m.group(1))
                total = m.group(2)
                break

        # -- Emoji grid for display (after the header, minus the score line) --
        grid_lines = [
            line.strip()
            for line in share_lines
            if line.strip() and self._score_re.search(line) is None
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