"""
Owner-only commands to register (or unregister) the bot's slash commands
with Discord. The bot also auto-syncs on startup, so these exist for when
you change a command and want to push the new tree without a restart.
"""

import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Context


class Sync(commands.Cog, name="sync"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.command(
        name="sync",
        description="Sync slash commands with Discord (global or guild).",
    )
    @app_commands.describe(scope="The scope of the sync. Can be `global` or `guild`")
    @commands.is_owner()
    async def sync(self, context: Context, scope: str) -> None:
        """
        Register the bot's slash commands with Discord.

        :param context: The command context.
        :param scope: The scope of the sync. Can be `global` or `guild`.
        """
        if scope == "global":
            await context.bot.tree.sync()
            description = "Slash commands have been globally synchronized."
        elif scope == "guild":
            context.bot.tree.copy_global_to(guild=context.guild)
            await context.bot.tree.sync(guild=context.guild)
            description = "Slash commands have been synchronized in this guild."
        else:
            embed = discord.Embed(
                description="The scope must be `global` or `guild`.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return
        embed = discord.Embed(description=description, color=0xBEBEFE)
        await context.send(embed=embed, silent=True)

    @commands.command(
        name="unsync",
        description="Remove the bot's slash commands (global or guild).",
    )
    @app_commands.describe(scope="The scope of the unsync. Can be `global` or `guild`")
    @commands.is_owner()
    async def unsync(self, context: Context, scope: str) -> None:
        """
        Unregister the bot's slash commands with Discord.

        :param context: The command context.
        :param scope: The scope of the unsync. Can be `global` or `guild`.
        """
        if scope == "global":
            context.bot.tree.clear_commands(guild=None)
            await context.bot.tree.sync()
            description = "Slash commands have been globally unsynchronized."
        elif scope == "guild":
            context.bot.tree.clear_commands(guild=context.guild)
            await context.bot.tree.sync(guild=context.guild)
            description = "Slash commands have been unsynchronized in this guild."
        else:
            embed = discord.Embed(
                description="The scope must be `global` or `guild`.",
                color=0xE02B2B,
            )
            await context.send(embed=embed, silent=True)
            return
        embed = discord.Embed(description=description, color=0xBEBEFE)
        await context.send(embed=embed, silent=True)


async def setup(bot) -> None:
    await bot.add_cog(Sync(bot))