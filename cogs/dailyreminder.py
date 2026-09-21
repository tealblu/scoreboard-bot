"""Daily games reminder."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands, tasks

from parsers import build_scoreboard_embed
from parsers.registry import discover_parsers
from timeutil import bot_tz, now, now_label, yesterday_str

if TYPE_CHECKING:
    from bot import TrivialBot
    from discord.ext.commands import Context

logger = logging.getLogger("trivial")

_REMINDER_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

_TZ_LABEL = str(bot_tz())  # e.g. "UTC" or "America/New_York"


class DailyReminder(commands.Cog, name="dailyreminder"):
    """Sends a daily reminder listing every supported game with a link."""

    def __init__(self, bot: TrivialBot) -> None:
        self.bot = bot
        self.parsers = discover_parsers()

    async def cog_load(self) -> None:
        """Start the reminder loop once the cog is added to the bot."""
        self.daily_reminder_loop.start()

    def cog_unload(self) -> None:
        self.daily_reminder_loop.cancel()

    @tasks.loop(minutes=1.0)
    async def daily_reminder_loop(self) -> None:
        """Every minute, fire reminders for guilds whose time has come."""
        current = now()
        current_time = current.strftime("%H:%M")
        today = current.strftime("%Y-%m-%d")

        for guild in self.bot.guilds:
            try:
                settings = await self.bot.database.get_daily_reminder(guild.id)
            except Exception:
                logger.exception(
                    "Could not read daily reminder settings for guild %s",
                    guild.name,
                )
                continue

            if not settings or not settings["enabled"]:
                continue
            if settings["reminder_time"] != current_time:
                continue
            if settings["last_fired"] == today:
                continue

            try:
                channel_id = await self.bot.database.get_score_channel(guild.id)
            except Exception:
                logger.exception(
                    "Could not read score channel for guild %s", guild.name
                )
                continue
            if channel_id is None:
                logger.info(
                    "Daily reminder for guild %s has no score channel to post to",
                    guild.name,
                )
                continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                logger.info(
                    "Daily reminder for guild %s could not find channel %s",
                    guild.name,
                    channel_id,
                )
                continue

            try:
                embeds = await self.build_reminder_embeds(
                    guild.id, channel, guild=guild
                )
                await channel.send(embeds=embeds, silent=True)
                await self.bot.database.mark_reminder_sent(guild.id, today)
                logger.info(
                    "Sent daily reminder to guild %s in #%s",
                    guild.name,
                    channel.name,
                )
            except Exception:
                logger.exception(
                    "Failed to send daily reminder to guild %s", guild.name
                )

    @daily_reminder_loop.before_loop
    async def before_daily_reminder_loop(self) -> None:
        await self.bot.wait_until_ready()

    def build_reminder_embed(self, channel: discord.abc.GuildChannel) -> discord.Embed:
        """List every supported game (with its link) in a Discord embed."""
        games = [parser for parser in self.parsers if not parser.hidden]
        games.sort(key=lambda parser: parser.game)

        lines: list[str] = []
        for parser in games:
            name = parser.game.title()
            if parser.game_url:
                host = urlparse(parser.game_url).netloc or parser.game_url
                lines.append(f"• **{name}** — [{host}]({parser.game_url})")
            else:
                logger.warning("Parser %s has no game_url", type(parser).__name__)
                lines.append(f"• **{name}**")

        embed = discord.Embed(
            title="🎮 Daily Games",
            description=(
                f"Time for today's games! Post your result in {channel.mention} "
                "to have it recorded.\n\n" + "\n".join(lines)
            ),
            color=0xBEBEFE,
        )
        embed.set_footer(text=f"Daily reminder · {now_label()}")
        return embed

    async def build_yesterday_scoreboard_embed(
        self, guild_id: int, guild: discord.Guild | None = None
    ) -> discord.Embed:
        """Build the previous day's scoreboard embed for *guild_id*."""
        yesterday = yesterday_str()
        records = await self.bot.database.get_scores(
            guild_id=guild_id, day=yesterday
        )
        sort_orders = {parser.game: parser.score_sort for parser in self.parsers}
        return build_scoreboard_embed(
            records,
            day=yesterday,
            title="📊 Yesterday's Scoreboard",
            color=0xBEBEFE,
            sort_orders=sort_orders,
            guild=guild,
        )

    async def build_reminder_embeds(
        self,
        guild_id: int,
        channel: discord.abc.GuildChannel,
        guild: discord.Guild | None = None,
    ) -> list[discord.Embed]:
        """The complete daily reminder as a list of embeds."""
        return [
            self.build_reminder_embed(channel),
            await self.build_yesterday_scoreboard_embed(guild_id, guild=guild),
        ]

    @commands.hybrid_group(
        name="dailyreminder",
        description="Manage the daily games reminder.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    async def dailyreminder(self, context: Context) -> None:
        """
        Manage the daily games reminder.

        :param context: The hybrid command context.
        """
        if context.invoked_subcommand is None:
            embed = discord.Embed(
                description="Please specify a subcommand.\n\n"
                "**Subcommands:**\n"
                "`enable` - Enable the daily reminder (posts to the score channel).\n"
                "`disable` - Disable the daily reminder.\n"
                "`time` - Set the reminder time (24-hour, e.g. `09:00`).\n"
                "`show` - Show the current reminder settings.\n"
                "`test` - Preview the daily reminder in this channel.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)

    @dailyreminder.command(
        name="enable",
        description="Enable the daily games reminder.",
    )
    @commands.has_permissions(manage_guild=True)
    async def dailyreminder_enable(self, context: Context) -> None:
        """
        Enable the daily games reminder in the server's score channel.
        """
        channel_id = await self.bot.database.get_score_channel(context.guild.id)
        if channel_id is None:
            embed = discord.Embed(
                description="No score channel is set for this server. "
                "Use `/scorechannel set` first so the reminder has somewhere to post.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        settings = await self.bot.database.get_daily_reminder(context.guild.id)
        reminder_time = settings["reminder_time"] if settings else "09:00"
        await self.bot.database.set_daily_reminder(
            context.guild.id, enabled=True, reminder_time=reminder_time
        )

        channel = context.guild.get_channel(channel_id)
        embed = discord.Embed(
            description=(
                f"Daily reminder enabled in "
                f"{channel.mention if channel else channel_id} at {reminder_time} ({_TZ_LABEL})."
            ),
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @dailyreminder.command(
        name="disable",
        description="Disable the daily games reminder.",
    )
    @commands.has_permissions(manage_guild=True)
    async def dailyreminder_disable(self, context: Context) -> None:
        """
        Disable the daily games reminder.
        """
        settings = await self.bot.database.get_daily_reminder(context.guild.id)
        if not settings or not settings["enabled"]:
            embed = discord.Embed(
                description="The daily reminder is already disabled.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        await self.bot.database.set_daily_reminder(
            context.guild.id,
            enabled=False,
            reminder_time=settings["reminder_time"],
        )
        embed = discord.Embed(
            description="Daily reminder disabled.",
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @dailyreminder.command(
        name="time",
        description="Set the daily reminder time (24-hour).",
    )
    @app_commands.describe(
        time="Reminder time in 24-hour format, e.g. 09:00 or 17:30"
    )
    @commands.has_permissions(manage_guild=True)
    async def dailyreminder_time(self, context: Context, time: str) -> None:
        """
        Set the daily reminder time in the bot's timezone.
        """
        match = _REMINDER_TIME_RE.match(time.strip())
        if match is None:
            embed = discord.Embed(
                description="Please use 24-hour time, e.g. `09:00` or `17:30`.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        normalized = f"{int(match.group(1)):02d}:{match.group(2)}"
        settings = await self.bot.database.get_daily_reminder(context.guild.id)
        enabled = bool(settings and settings["enabled"])
        await self.bot.database.set_daily_reminder(
            context.guild.id, enabled=enabled, reminder_time=normalized
        )

        state = "enabled" if enabled else "saved (reminder is disabled)"
        embed = discord.Embed(
            description=f"Daily reminder time set to {normalized} ({_TZ_LABEL}) ({state}).",
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @dailyreminder.command(
        name="show",
        description="Show the current daily reminder settings.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def dailyreminder_show(self, context: Context) -> None:
        """
        Show the current daily reminder settings.

        :param context: The hybrid command context.
        """
        settings = await self.bot.database.get_daily_reminder(context.guild.id)
        if settings is None:
            embed = discord.Embed(
                description="No daily reminder configured for this server. "
                "Use `/dailyreminder enable` to set one up.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        state = "enabled" if settings["enabled"] else "disabled"
        channel_id = await self.bot.database.get_score_channel(context.guild.id)
        channel = context.guild.get_channel(channel_id) if channel_id else None

        lines = [
            f"**Status:** {state}",
            f"**Time:** {settings['reminder_time']} ({_TZ_LABEL})",
        ]
        if channel:
            lines.append(f"**Channel:** {channel.mention}")
        elif channel_id:
            lines.append(f"**Channel:** {channel_id}")
        else:
            lines.append("**Channel:** none set — use `/scorechannel set` first.")

        embed = discord.Embed(
            title="⏰ Daily Reminder",
            description="\n".join(lines),
            color=0xBEBEFE,
        )
        await context.send(embed=embed, silent=True)

    @dailyreminder.command(
        name="test",
        description="Preview the daily reminder in this channel.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def dailyreminder_test(self, context: Context) -> None:
        """
        Send the daily reminder to the current channel
        """
        channel_id = await self.bot.database.get_score_channel(context.guild.id)
        score_channel = context.guild.get_channel(channel_id) if channel_id else None

        reference = score_channel or context.channel
        embeds = await self.build_reminder_embeds(
            context.guild.id, reference, guild=context.guild
        )
        await context.send(embeds=embeds, silent=True)


async def setup(bot: TrivialBot) -> None:
    await bot.add_cog(DailyReminder(bot))
