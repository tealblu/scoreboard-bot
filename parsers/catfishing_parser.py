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

    A comment may precede the share — anything above the header line is
    ignored::

        easily could have been 8
        catfishing.net
        #819 - 5/10
        🐈🐟🐈🐟🐈
        🐈🐟🐈🐟🐟

    ``4/10`` is correct guesses out of 10 rounds — the numerator is the
    recorded score (higher is better). The puzzle number (#815) and
    round total are stored in meta; the grid is shown in the embed for
    context. Like other daily games, the score is tied to the day it
    was posted (in the bot's timezone).
    """

    game = "catfishing"
    score_sort = "desc"  # higher score is better
    game_url = "https://catfishing.net"

    # The share header is the FIRST line, alone on that line: either
    # "catfishing.net" or "catfishing dot net". Anchored to the whole line
    # (not just the word anywhere) so prose like "…done a catfishing since
    # 9/17…" never looks like a share.
    _header_re = re.compile(
        r"\s*catfishing(?:\s*dot\s*net|\.net)?\s*$", re.IGNORECASE
    )
    # "#815 - 4/10" — puzzle number and correct/total score.
    _number_re = re.compile(r"#\s*(\d+)")
    _score_re = re.compile(r"(\d+)\s*/\s*(\d+)")
    # Catfishing shares are always "X/10" — correct guesses out of 10 rounds.
    # Requiring the total filters out date-like fractions ("since 9/17").
    _total = "10"

    async def can_parse(self, message: discord.Message) -> bool:
        # The share header is its own whole line — "catfishing.net" or
        # "catfishing dot net" — and arbitrary prose may precede it (e.g.
        # "easily could have been 8"). A "X/10" score line must follow the
        # header. Casual mentions of the game, or a stray date fraction
        # ("since 9/17"), still can't match.
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

        # The share starts at the header line ("catfishing.net" /
        # "catfishing dot net"); any lines before it are preamble (e.g. a
        # comment) and are ignored.
        header_index = next(
            (i for i, line in enumerate(lines) if self._header_re.match(line)),
            None,
        )
        share_lines = lines[header_index + 1 :] if header_index is not None else lines

        # -- Puzzle number ("#819 - 5/10") — search the share only, so
        #    preamble text can't hijack the number --
        number = ""
        for line in share_lines:
            m = self._number_re.search(line)
            if m:
                number = m.group(1)
                break

        # -- Score: "X/10" — record the numerator --
        # Only a line whose total is the game's 10 rounds counts as the
        # score (can_parse guarantees at least one follows the header).
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