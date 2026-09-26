from __future__ import annotations

import logging
import re

import discord

from .base import ScoreParser, ScoreResponse, member_display_name

logger = logging.getLogger("trivial")


class WordleScoreParser(ScoreParser):
    """Parser for the Wordle share grid.

    sent by the player:
        Wordle 1925 4/6

        ⬛⬛⬛⬛🟨
        ⬛🟩⬛⬛⬛
        🟩🟩⬛⬛🟨
        🟩🟩⬛⬛🟨
        🟩🟩⬛⬛🟨
        ⬜⬜⬜⬜⬜

    sent by the wordle bot for the player, either as a reply to their
    message or as the response to their /share
    """

    game = "wordle"
    score_sort = "asc"  # fewer guesses is better
    game_url = "https://www.nytimes.com/games/wordle/index.html"
    reads_bot_messages = True  # the bot posts the grid for the player

    # "Wordle 1925 4/6" or "Wordle 1,925 X/6"
    _header_re = re.compile(
        r"\bWordle\s*#?\s*(?P<number>\d{1,5}(?:,\d{3})*)\s+"
        r"(?P<guesses>\d+|[xX])\s*/\s*(?P<total>\d+)",
        re.IGNORECASE,
    )
    # one row is 5 tiles: green yellow guessed or blank
    _row_re = re.compile(r"[\U0001f7e8\U0001f7e9\u2b1b\u2b1c]{5}")
    _blank = "\u2b1c"  # ⬜ pads a share out to 6 rows

    def can_parse(self, message: discord.Message) -> bool:
        if self._header_re.search(message.content) is None:
            return False
        if not self._rows(message.content):
            return False
        # a bot post needs a player to credit
        if self._player(message) is None:
            logger.info(
                "Wordle share from %s in %s has no player to credit",
                message.author,
                message.channel,
            )
            return False
        return True

    def parse(self, message: discord.Message) -> ScoreResponse:
        header = self._header_re.search(message.content)
        number = header.group("number")
        guesses = header.group("guesses").upper()
        total = header.group("total")
        rows = self._rows(message.content)

        # the grid says how many guesses it took
        score = sum(1 for row in rows if self._blank not in row)
        if not score:
            score = int(total) if guesses == "X" else int(guesses)

        player = self._player(message)
        resp = self._build_response(message, title="Wordle", score=score)
        resp.user_id = player.id
        resp.username = member_display_name(player, message.guild)
        resp.meta.update(
            number=number.replace(",", ""),
            guesses=guesses,
            total=total,
            grid="\n".join(rows),
        )
        resp.description = "\n".join(
            [f"Wordle {number} {guesses}/{total}", "", *rows]
        )
        return resp

    def _rows(self, content: str) -> list[str]:
        """Grid rows in the order they appear."""
        return self._row_re.findall(content)

    def _player(self, message: discord.Message) -> discord.User | None:
        """Who the score belongs to: the sender, or whoever the bot posted for."""
        if not message.author.bot:
            return message.author
        # a text reply names the player
        reference = message.reference
        replied_to = reference.resolved if reference is not None else None
        author = replied_to.author if replied_to is not None else None
        if author is not None and not author.bot:
            return author
        # a /share response names whoever ran the command
        metadata = message.interaction_metadata
        invoker = metadata.user if metadata is not None else None
        if invoker is not None and not invoker.bot:
            return invoker
        return None
