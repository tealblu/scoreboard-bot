from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from parsers import ScoreParser, select_parser, build_scoreboard_embed
from parsers.base import _utc_today
from parsers.registry import discover_parsers

if TYPE_CHECKING:
    from bot import TrivialBot
    from discord.ext.commands import Context

logger = logging.getLogger("trivial")


class Scoreboard(commands.Cog):
    """Listens for messages containing game scores and posts parsed results."""

    def __init__(self, bot: TrivialBot) -> None:
        self.bot = bot
        self._tracked_channels: dict[int, int] = {}  # guild_id -> channel_id

        # -------------------------------------------------------------- #
        # Parsers are auto-discovered from the parsers/ package —         #
        # adding a new game = dropping one file, nothing else to edit.    #
        # -------------------------------------------------------------- #
        self.parsers: list[ScoreParser] = discover_parsers()
        for parser in self.parsers:
            logger.info(
                "Registered parser: %s (game: %s)", type(parser).__name__, parser.game
            )

    # ------------------------------------------------------------------ #
    # Parser management                                                  #
    # ------------------------------------------------------------------ #

    def add_parser(self, parser: ScoreParser) -> None:
        """Manually append a parser instance (for special cases).

        Parsers are checked in registration order by ``select_parser``;
        the first one whose ``can_parse`` returns ``True`` wins.
        """
        self.parsers.append(parser)
        logger.info("Registered parser: %s", type(parser).__name__)

    # ------------------------------------------------------------------ #
    # Channel tracking                                                   #
    # ------------------------------------------------------------------ #

    async def _get_tracked_channel(self, guild_id: int) -> int | None:
        """Return the monitored channel ID for *guild_id*, or None.

        Results are cached in memory after the first lookup per guild.
        """
        if guild_id not in self._tracked_channels:
            self._tracked_channels[guild_id] = (
                await self.bot.database.get_score_channel(guild_id)
            )
        return self._tracked_channels[guild_id]

    # ------------------------------------------------------------------ #
    # Commands                                                           #
    # ------------------------------------------------------------------ #

    @commands.hybrid_group(
        name="scorechannel",
        description="Manage the channel trivial monitors for scores.",
    )
    @commands.guild_only()
    async def scorechannel(self, context: Context) -> None:
        """
        Manage the channel trivial monitors for scores.

        :param context: The hybrid command context.
        """
        if context.invoked_subcommand is None:
            embed = discord.Embed(
                description="Please specify a subcommand.\n\n**Subcommands:**\n`set` - Set the channel to monitor for scores.\n`remove` - Stop monitoring scores in this server.\n`show` - Show the currently monitored channel.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)

    @scorechannel.command(
        name="set",
        description="Set the channel trivial monitors for scores.",
    )
    @commands.has_permissions(manage_channels=True)
    @app_commands.describe(channel="The channel to monitor for score messages.")
    async def scorechannel_set(
        self, context: Context, channel: discord.TextChannel
    ) -> None:
        """
        Set the channel trivial monitors for scores.

        :param context: The hybrid command context.
        :param channel: The channel to monitor for score messages.
        """
        await self.bot.database.set_score_channel(context.guild.id, channel.id)
        self._tracked_channels[context.guild.id] = channel.id
        embed = discord.Embed(
            description=f"Now monitoring scores in {channel.mention}.",
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @scorechannel.command(
        name="remove",
        description="Stop monitoring scores in this server.",
    )
    @commands.has_permissions(manage_channels=True)
    async def scorechannel_remove(self, context: Context) -> None:
        """
        Stop monitoring scores in this server.

        :param context: The hybrid command context.
        """
        await self.bot.database.remove_score_channel(context.guild.id)
        self._tracked_channels.pop(context.guild.id, None)
        embed = discord.Embed(
            description="Stopped monitoring scores in this server.",
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @scorechannel.command(
        name="show",
        description="Show the currently monitored score channel.",
    )
    @commands.guild_only()
    async def scorechannel_show(self, context: Context) -> None:
        """
        Show the currently monitored score channel.

        :param context: The hybrid command context.
        """
        channel_id = await self._get_tracked_channel(context.guild.id)
        if channel_id is None:
            embed = discord.Embed(
                description="No score channel is set for this server. Use `/scorechannel set` to configure one.",
                color=0xE02B2B,
            )
        else:
            channel = context.guild.get_channel(channel_id)
            embed = discord.Embed(
                description=f"Trivial monitors scores in {channel.mention if channel else channel_id}.",
                color=0xBEBEFE,
            )
        await context.send(embed=embed, silent=True)

    # ------------------------------------------------------------------ #
    # Score queries                                                       #
    # ------------------------------------------------------------------ #

    @commands.command(name="scores", help="Show the score leaderboard.")
    @commands.guild_only()
    async def scores(self, context: Context, game: str = None, day: str = None) -> None:
        """
        Show the score leaderboard for this guild.

        Usage:
            !scores                   — today's scores, all games
            !scores wordle            — today's wordle scores
            !scores wordle 2026-09-17 — wordle scores for a specific date

        :param context: The command context.
        :param game: Optional game identifier to filter by.
        :param day: Optional date (YYYY-MM-DD) to filter by.
        """
        if day is None:
            day = _utc_today()

        records = await context.bot.database.get_scores(
            guild_id=context.guild.id,
            game=game,
            day=day,
        )
        sort_orders = {p.game: p.score_sort for p in self.parsers}
        embed = build_scoreboard_embed(
            records, game=game, day=day, sort_orders=sort_orders
        )
        await context.send(embed=embed, silent=True)

    # ------------------------------------------------------------------ #
    # Nuke                                                               #
    # ------------------------------------------------------------------ #

    @commands.hybrid_command(
        name="nuke",
        description="Delete all recorded scores for this server (admins only).",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(
        confirm="Type 'confirm' to permanently delete this server's scores."
    )
    async def nuke(self, context: Context, confirm: str = "") -> None:
        """
        Delete every recorded score for this server.

        Only this server's leaderboard rows are removed — the monitored
        score channel and daily reminder settings are kept, and the other
        servers' scores are untouched.

        Usage:
            !nuke          — shows what this command does
            !nuke confirm  — permanently deletes this server's scores

        :param context: The hybrid command context.
        :param confirm: Must be "confirm" to actually delete.
        """
        if confirm.strip().lower() != "confirm":
            embed = discord.Embed(
                description=(
                    "⚠️ This **permanently deletes every recorded score** for "
                    f"**{context.guild.name}** — today's and all-time "
                    "leaderboards will start empty.\n\n"
                    "Channel and reminder settings are kept, and no other "
                    "server's scores are affected.\n\n"
                    "Run `/nuke confirm` (or `!nuke confirm`) to proceed."
                ),
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        deleted = await self.bot.database.delete_guild_scores(context.guild.id)
        embed = discord.Embed(
            description=(
                f"💥 Deleted **{deleted}** score{'s' if deleted != 1 else ''} "
                f"for **{context.guild.name}**. Leaderboards are now empty."
            ),
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    # ------------------------------------------------------------------ #
    # Event listeners                                                    #
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return

        # Only parse messages in the configured channel
        tracked_channel = await self._get_tracked_channel(message.guild.id)
        if tracked_channel is None or message.channel.id != tracked_channel:
            return

        # 1. Decide which parser handles this message (one parser per game)
        parser = await select_parser(self.parsers, message)
        if parser is None:
            return

        try:
            # 2. Extract the user's score for that game
            score_response = await parser.parse(message)
            # 3. Persist ONE score for the game BEFORE posting, so a daily
            #    result is never lost even if the embed fails.
            await parser.record_score(message, score_response, self.bot.database)
            # 4. Post the formatted result to the channel
            embed = await parser.format_response(score_response)
            await message.channel.send(embed=embed, silent=True)
            logger.info(
                "Recorded %s score for %s in #%s using %s",
                parser.game,
                message.author,
                message.channel,
                type(parser).__name__,
            )
        except Exception:
            logger.exception(
                "Parser %s failed on message %s",
                type(parser).__name__,
                message.id,
            )


async def setup(bot: TrivialBot) -> None:
    await bot.add_cog(Scoreboard(bot))