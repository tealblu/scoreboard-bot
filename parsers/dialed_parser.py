from __future__ import annotations

import re
from datetime import datetime, timezone

import discord

from .base import ScoreParser, ScoreResponse

_MONTH_ABBR = {
    name.lower(): idx
    for idx, name in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        start=1,
    )
}


class DialedScoreParser(ScoreParser):
    """Parser for dialed.gg daily scores — specifically the Color Daily.

    Dialed offers several games (Color, Sound, Time, Shape) across solo,
    multiplayer and daily modes. Only the daily is tracked here, so this
    parser matches exclusively on the ``Color Daily`` share header::

        Color Daily — Sep 18
        40.49/50 🟩🟨🟨🟧🟨
        https://dialed.gg/color?d=1&s=40.49

    The exact score (e.g. 40.49) is what gets recorded — unlike most
    games here the score is a decimal, out of 50 (higher is better). The
    per-round tiles and the total are echoed in the embed for context.
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

    async def can_parse(self, message: discord.Message) -> bool:
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

    async def parse(self, message: discord.Message) -> ScoreResponse:
        lines = message.content.strip().splitlines()

        # -- Exact score and total from the "X/50" line --
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

        # -- Date from the header line ("Color Daily — Sep 18") --
        day = self._parse_date(lines[0]) if lines else None

        # -- Per-round tiles, e.g. 🟩🟨🟨🟧🟨 (the rest of the score line) --
        tiles = ""
        for line in lines:
            match = self._score_re.search(line)
            if match:
                tiles = self._score_re.sub("", line).strip()
                break

        # -- Build the response --
        resp = ScoreResponse(
            title="Color Daily",
            score=score,
            game=self.game,
            user_id=message.author.id,
            username=message.author.display_name,
        )
        if day:
            resp.day = day
        if raw_score:
            resp.meta["score"] = raw_score
        if total:
            resp.meta["total"] = total
        if tiles:
            resp.meta["tiles"] = tiles

        # Echo the share verbatim (header + score line) in the embed.
        header = lines[0].strip() if lines else "Color Daily"
        score_line = " ".join(
            part for part in (f"{raw_score or ''}/{total or ''}".rstrip("/"), tiles) if part
        )
        resp.description = "\n".join([header, score_line])

        return resp

    async def format_response(self, score_response: ScoreResponse) -> discord.Embed:
        embed = discord.Embed(
            title=score_response.title,
            description=score_response.description,
            color=score_response.color,
        )
        score = score_response.score
        embed.add_field(name="Score", value=self._fmt(score), inline=True)
        embed.set_footer(text=f"{score_response.username} · {score_response.day}")
        return embed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt(score: int | float | None) -> str:
        """Render a score for display: 40.49 → '40.49', 50.0 → '50'."""
        if score is None:
            return "—"
        if isinstance(score, float) and score.is_integer():
            return str(int(score))
        return str(score)

    @classmethod
    def _parse_date(cls, text: str) -> str | None:
        """Parse a date like ``Sep 18`` into ``YYYY-MM-DD``.

        Uses the current UTC year, rewinding a year if the resulting date
        is in the future (e.g. a "Dec 31 ..." score posted on Jan 1).
        """
        match = cls._date_re.search(text)
        if match is None:
            return None

        month = _MONTH_ABBR.get(match.group(1).lower())
        if month is None:
            return None
        try:
            day_num = int(match.group(2))
        except ValueError:
            return None

        now = datetime.now(timezone.utc)
        try:
            date = datetime(now.year, month, day_num)
        except ValueError:
            return None

        if date.date() > now.date():
            date = date.replace(year=now.year - 1)
        return date.strftime("%Y-%m-%d")