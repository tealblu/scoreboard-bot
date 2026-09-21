from __future__ import annotations

import re

import discord

from .base import ScoreParser, ScoreResponse, message_author_display_name
from .common import format_score, parse_month_day


class DialedScoreParser(ScoreParser):
    """Parser for dialed.gg daily scores — specifically the Color Daily.
        Color Daily — Sep 18
        40.49/50 🟩🟨🟨🟧🟨
        https://dialed.gg/color?d=1&s=40.49

    """

    game = "dialed"
    score_sort = "desc"  # higher score is better
    game_url = "https://dialed.gg/color"

    # The daily share header — everything else dialed posts is ignored.
    _header_re = re.compile(r"Color\s+Daily", re.IGNORECASE)
    # Score line "40.49/50" (the share URL's s= param has no "/50").
    _score_re = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*(\d+)")
    # Date inside the header, e.g. "Sep 18".
    _date_re = re.compile(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\b",
        re.IGNORECASE,
    )

    def can_parse(self, message: discord.Message) -> bool:
        content = message.content
        # Only the Color Daily share — other dialed games/modes never match.
        if self._header_re.search(content) is None:
            return False
        # Require the share URL AND a "X/50" score line so a text-only
        # mention of the site doesn't match (and can't record a None score).
        if "dialed.gg" not in content:
            return False
        match = self._score_re.search(content)
        return match is not None and match.group(2) == "50"

    def parse(self, message: discord.Message) -> ScoreResponse:
        lines = message.content.strip().splitlines()

        score: float | None = None
        total: str | None = None
        raw_score: str | None = None
        for line in lines:
            match = self._score_re.search(line)
            if match:
                raw_score = match.group(1)
                total = match.group(2)
                score = float(raw_score)
                break

        day = None
        if lines:
            date_match = self._date_re.search(lines[0])
            if date_match is not None:
                day = parse_month_day(date_match.group(1), int(date_match.group(2)))

        tiles = ""
        for line in lines:
            match = self._score_re.search(line)
            if match:
                tiles = self._score_re.sub("", line).strip()
                break

        resp = ScoreResponse(
            title="Color Daily",
            score=score,
            game=self.game,
            user_id=message.author.id,
            username=message_author_display_name(message),
        )
        if day:
            resp.day = day
        if raw_score:
            resp.meta["score"] = raw_score
        if total:
            resp.meta["total"] = total
        if tiles:
            resp.meta["tiles"] = tiles

        header = lines[0].strip() if lines else "Color Daily"
        score_line = " ".join(
            part for part in (f"{raw_score or ''}/{total or ''}".rstrip("/"), tiles) if part
        )
        resp.description = "\n".join([header, score_line])

        return resp

    def format_response(self, score_response: ScoreResponse) -> discord.Embed:
        embed = discord.Embed(
            title=score_response.title,
            description=score_response.description,
            color=score_response.color,
        )
        score = score_response.score
        embed.add_field(name="Score", value=format_score(score), inline=True)
        embed.set_footer(text=f"{score_response.username} · {score_response.day}")
        return embed
