from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from parsers import ScoreParser, select_parser, build_scoreboard_embed
from parsers.registry import discover_parsers
from timeutil import day_string, today_str

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
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
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
    @commands.has_permissions(manage_guild=True)
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
    @commands.has_permissions(manage_guild=True)
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
    @commands.has_permissions(manage_guild=True)
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

    @commands.hybrid_command(
        name="scores",
        description="Show the score leaderboard.",
        help="Show the score leaderboard.",
    )
    @commands.guild_only()
    @app_commands.describe(
        game="Optional game identifier to filter by, e.g. wordle.",
        day="Optional date (YYYY-MM-DD) to filter by.",
    )
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
        # Ack immediately — the leaderboard query over a large (e.g. freshly
        # backfilled) table can outlast Discord's 3-second interaction window.
        # Deferring turns the response into a followup and gives us 15 minutes,
        # avoiding "Unknown interaction" (10062) errors.
        await context.defer()

        if day is None:
            day = today_str()

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
    @app_commands.default_permissions(manage_guild=True)
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
    # Backfill                                                           #
    # ------------------------------------------------------------------ #

    @commands.hybrid_command(
        name="backfill",
        description="Record score messages from the score channel's history.",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        limit="How many messages to scan (default: 200; 0 = all history).",
        days="Only scan messages posted in the last N days (default: all).",
    )
    async def backfill(
        self,
        context: Context,
        limit: int = 200,
        days: int | None = None,
    ) -> None:
        """
        Scan the score channel's message history and record any score
        messages into the database — without posting result embeds.

        Handy right after enabling a score channel, so leaderboards can be
        filled from messages posted before trivial was watching. Re-running
        is safe: same-day scores for the same user are overwritten.

        Usage:
            !backfill         — scan the last 200 messages
            !backfill 1000    — scan the last 1000 messages
            !backfill 0       — scan the entire history
            !backfill 0 7     — entire history but only the last 7 days

        :param context: The hybrid command context.
        :param limit: Maximum number of messages to scan (0 = no limit).
        :param days: Only scan messages newer than this many days.
        """
        channel_id = await self._get_tracked_channel(context.guild.id)
        if channel_id is None:
            embed = discord.Embed(
                description="No score channel is set for this server. Use `/scorechannel set` first.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        channel = context.guild.get_channel(channel_id)
        if channel is None:
            embed = discord.Embed(
                description="The configured score channel could not be found.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return

        limit_desc = "all" if limit <= 0 else f"up to **{limit}**"
        await context.send(
            embed=discord.Embed(
                description=f"🔍 Scanning {limit_desc} messages in {channel.mention}…",
                color=0xBEBEFE,
            ),
            silent=True,
        )

        kwargs: dict = {}
        if limit > 0:
            kwargs["limit"] = limit
        if days is not None:
            kwargs["after"] = datetime.now(timezone.utc) - timedelta(days=days)

        scanned = 0
        recorded = 0
        games: dict[str, int] = {}
        now_day = today_str()
        # (author, game, day) keys already recorded on this run. History is
        # iterated newest-first, so a duplicate same-day post for the same
        # player/game must NOT overwrite the newer one just seen: skip it.
        seen: set[tuple[int, str, str]] = set()

        async for message in channel.history(**kwargs):
            if message.author.bot:
                continue
            scanned += 1
            try:
                parser = await select_parser(self.parsers, message)
                if parser is None:
                    continue
                response = await parser.parse(message)
                # Parsers default the day to "today" when the share text
                # carries no date (Krillion, Wordle, ...). When backfilling
                # old messages that's the wrong day — fall back to the
                # message's own posting date (in the bot's timezone) unless
                # the message itself was posted today (or the parser picked
                # an explicit date).
                message_day = day_string(message.created_at)
                if response.day != message_day and response.day == now_day:
                    response.day = message_day
                key = (message.author.id, parser.game, response.day)
                if key in seen:
                    continue  # a newer post for this player/game/day is recorded
                seen.add(key)
                await parser.record_score(message, response, self.bot.database)
                recorded += 1
                games[parser.game] = games.get(parser.game, 0) + 1
            except Exception:
                logger.exception(
                    "Backfill: parser %s failed on message %s",
                    type(parser).__name__ if parser else "?",
                    message.id,
                )

        game_list = ", ".join(
            f"{name} × {count}" for name, count in sorted(games.items())
        )
        embed = discord.Embed(
            description=(
                f"✅ Scanned **{scanned}** message(s) in {channel.mention}.\n"
                f"Recorded **{recorded}** score(s)"
                + (f" ({game_list})" if game_list else "")
                + ".\n"
                "No embeds were posted. Re-running is safe — same-day "
                "scores for the same user simply overwrite (newest post wins)."
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