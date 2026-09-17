from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from parsers import ScoreParser
from parsers.example_parser import ExampleScoreParser

if TYPE_CHECKING:
    from bot import DiscordBot
    from discord.ext.commands import Context

logger = logging.getLogger("discord_bot")


class Scoreboard(commands.Cog):
    """Listens for messages containing game scores and posts parsed results."""

    def __init__(self, bot: DiscordBot) -> None:
        self.bot = bot
        self.parsers: list[ScoreParser] = []
        self._tracked_channels: dict[int, int] = {}  # guild_id -> channel_id

        # --- Register parsers here ---
        self.add_parser(ExampleScoreParser())

    # ------------------------------------------------------------------ #
    # Parser management                                                  #
    # ------------------------------------------------------------------ #

    def add_parser(self, parser: ScoreParser) -> None:
        """Register a ScoreParser instance.

        Parsers are checked in insertion order; the first one whose
        ``can_parse`` returns ``True`` wins.
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
        description="Manage the channel the bot monitors for scores.",
    )
    @commands.guild_only()
    async def scorechannel(self, context: Context) -> None:
        """
        Manage the channel the bot monitors for scores.

        :param context: The hybrid command context.
        """
        if context.invoked_subcommand is None:
            embed = discord.Embed(
                description="Please specify a subcommand.\n\n**Subcommands:**\n`set` - Set the channel to monitor for scores.\n`remove` - Stop monitoring scores in this server.\n`show` - Show the currently monitored channel.",
                color=0xE02B2B,
            )
            await context.send(embed=embed)

    @scorechannel.command(
        name="set",
        description="Set the channel the bot monitors for scores.",
    )
    @commands.has_permissions(manage_channels=True)
    @app_commands.describe(channel="The channel to monitor for score messages.")
    async def scorechannel_set(
        self, context: Context, channel: discord.TextChannel
    ) -> None:
        """
        Set the channel the bot monitors for scores.

        :param context: The hybrid command context.
        :param channel: The channel to monitor for score messages.
        """
        await self.bot.database.set_score_channel(context.guild.id, channel.id)
        self._tracked_channels[context.guild.id] = channel.id
        embed = discord.Embed(
            description=f"Now monitoring scores in {channel.mention}.",
            color=0xBEBEFE,
        )
        await context.send(embed=embed)

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
        await context.send(embed=embed)

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
                description=f"The bot monitors scores in {channel.mention if channel else channel_id}.",
                color=0xBEBEFE,
            )
        await context.send(embed=embed)

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

        for parser in self.parsers:
            try:
                if await parser.can_parse(message):
                    score_response = await parser.parse(message)
                    embed = await parser.format_response(score_response)
                    await message.channel.send(embed=embed)
                    logger.info(
                        "Parsed scores from %s in #%s using %s",
                        message.author,
                        message.channel,
                        type(parser).__name__,
                    )
                    return  # first matching parser wins
            except Exception:
                logger.exception(
                    "Parser %s failed on message %s",
                    type(parser).__name__,
                    message.id,
                )


async def setup(bot: DiscordBot) -> None:
    await bot.add_cog(Scoreboard(bot))