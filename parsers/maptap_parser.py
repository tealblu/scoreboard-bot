from __future__ import annotations

import re
from datetime import datetime

import discord

from timeutil import now as bot_now

from .base import ScoreParser, ScoreResponse, message_author_display_name


class MapTapScoreParser(ScoreParser):
    """Parser for www.maptap.gg daily scores.
        www.maptap.gg September 17
        93🏆 99🎯 98🎯 87🎓 62😐
        Final score: 835
    """

    game = "maptap"
    score_sort = "desc"  # higher score is better
    game_url = "https://www.maptap.gg"

    _MONTH_NAMES = {name.lower(): idx for idx, name in enumerate(
        ["January", "February", "March", "April", "May", "June",
         "July", "August", "September", "October", "November", "December"],
        start=1,
    )}

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

        # -- Parse the total score --
        score = None
        for line in reversed(lines):
            m = re.search(r"Final score:\s*(\d+)", line, re.IGNORECASE)
            if m:
                score = int(m.group(1))
                break

        # -- Parse the date from the first line --
        day = None
        if lines:
            first = lines[0].strip()
            # Remove the URL prefix to isolate the date text.
            first = re.sub(r"www\.maptap\.gg\s*", "", first).strip()
            day = self._parse_date(first)

        # -- Parse individual round scores --
        rounds: list[str] = []
        for line in lines:
            for match in self._round_re.finditer(line):
                rounds.append(f"{match.group(1)}{match.group(2)}")

        # -- Build the response --
        resp = ScoreResponse(
            title="MapTap",
            score=score,
            game=self.game,
            user_id=message.author.id,
            username=message_author_display_name(message),
        )

        if day:
            resp.day = day

        # Show round breakdown in the embed.
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

    # helpers
    @classmethod
    def _parse_date(cls, text: str) -> str | None:
        """Try to parse a date like ``September 17`` into ``YYYY-MM-DD``."""
        # Strip any trailing timezone info or stray characters.
        text = text.strip().rstrip(".")
        parts = text.split()
        if len(parts) != 2:
            return None

        month_name, day_str = parts
        month = cls._MONTH_NAMES.get(month_name.lower())
        if month is None:
            return None

        try:
            day_num = int(day_str)
        except ValueError:
            return None

        now = bot_now()
        year = now.year
        try:
            date = datetime(year, month, day_num)
        except ValueError:
            return None

        # A date in the future means the share is from an earlier year
        if date.date() > now.date():
            date = date.replace(year=year - 1)
        return date.strftime("%Y-%m-%d")
