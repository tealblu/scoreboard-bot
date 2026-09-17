"""
Copyright © Krypton 2019-Present - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized Discord bot in Python

Version: 6.5.0
"""

import json

import aiosqlite


class DatabaseManager:
    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    async def set_score_channel(self, server_id: int, channel_id: int) -> None:
        """
        Set the channel that trivial monitors for scores in a server.

        :param server_id: The ID of the server.
        :param channel_id: The ID of the channel to monitor.
        """
        await self.connection.execute(
            "INSERT INTO score_channels(server_id, channel_id) VALUES (?, ?) "
            "ON CONFLICT(server_id) DO UPDATE SET channel_id=excluded.channel_id",
            (
                server_id,
                channel_id,
            ),
        )
        await self.connection.commit()

    async def get_score_channel(self, server_id: int) -> int | None:
        """
        Get the channel that trivial monitors for scores in a server.

        :param server_id: The ID of the server.
        :return: The ID of the monitored channel, or None if not set.
        """
        rows = await self.connection.execute(
            "SELECT channel_id FROM score_channels WHERE server_id=?",
            (server_id,),
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            return int(result[0]) if result is not None else None

    async def remove_score_channel(self, server_id: int) -> None:
        """
        Remove the monitored score channel from a server.

        :param server_id: The ID of the server.
        """
        await self.connection.execute(
            "DELETE FROM score_channels WHERE server_id=?",
            (server_id,),
        )
        await self.connection.commit()

    async def set_daily_reminder(
        self,
        server_id: int,
        enabled: bool,
        reminder_time: str,
    ) -> None:
        """
        Upsert the daily reminder settings for a server.

        Updating settings also clears ``last_fired`` so the reminder can
        fire again at the (possibly new) time on the current day.

        :param server_id: The ID of the server.
        :param enabled: Whether the daily reminder is enabled.
        :param reminder_time: "HH:MM" in UTC (24-hour).
        """
        await self.connection.execute(
            "INSERT INTO daily_reminders(server_id, enabled, reminder_time) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(server_id) DO UPDATE SET "
            "enabled=excluded.enabled, reminder_time=excluded.reminder_time, "
            "last_fired=NULL, updated_at=CURRENT_TIMESTAMP",
            (
                str(server_id),
                1 if enabled else 0,
                reminder_time,
            ),
        )
        await self.connection.commit()

    async def get_daily_reminder(self, server_id: int) -> dict | None:
        """
        Get the daily reminder settings for a server, or None if unset.

        :param server_id: The ID of the server.
        :return: ``{enabled, reminder_time, last_fired}`` or None.
        """
        rows = await self.connection.execute(
            "SELECT enabled, reminder_time, last_fired "
            "FROM daily_reminders WHERE server_id=?",
            (str(server_id),),
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            if result is None:
                return None
            return {
                "enabled": bool(result[0]),
                "reminder_time": result[1],
                "last_fired": result[2],
            }

    async def mark_reminder_sent(self, server_id: int, day: str) -> None:
        """
        Record that the daily reminder was sent for *day* so it doesn't re-fire.

        :param server_id: The ID of the server.
        :param day: The date (YYYY-MM-DD) the reminder was sent.
        """
        await self.connection.execute(
            "UPDATE daily_reminders SET last_fired=? WHERE server_id=?",
            (day, str(server_id)),
        )
        await self.connection.commit()

    async def record_user_score(
        self,
        guild_id: int,
        user_id: int,
        user_name: str,
        game: str,
        day: str,
        score: int | None,
        meta: dict | None = None,
    ) -> None:
        """
        Log one user's score for one game on one day.

        One row per (guild_id, user_id, game, day): re-posting a daily
        score for the same day overwrites the previous value.

        :param guild_id: The ID of the guild the message was posted in.
        :param user_id: The ID of the user who posted the score.
        :param user_name: The user's display name (for logging/embeds).
        :param game: The game identifier, e.g. "wordle" (matches parser.game).
        :param day: The date this score belongs to, YYYY-MM-DD.
        :param score: The numeric score to record.
        :param meta: Optional extra per-game details, stored as JSON.
        """
        if score is None:
            raise ValueError("record_user_score requires a numeric score; parser did not set ScoreResponse.score")

        await self.connection.execute(
            "INSERT INTO user_scores (guild_id, user_id, user_name, game, day, score, meta) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(guild_id, user_id, game, day) DO UPDATE SET "
            "score = excluded.score, user_name = excluded.user_name, "
            "meta = excluded.meta, created_at = CURRENT_TIMESTAMP",
            (
                str(guild_id),
                str(user_id),
                user_name,
                game,
                day,
                score,
                json.dumps(meta) if meta else None,
            ),
        )
        await self.connection.commit()

    async def get_scores(
        self,
        guild_id: int,
        game: str | None = None,
        day: str | None = None,
    ) -> list:
        """
        Fetch leaderboard rows for a guild, optionally filtered by game and/or day.

        Results are ordered by game (alphabetical) then score (ascending,
        lower = better for daily games).  Each row is a
        :class:`~parsers.base.ScoreRecord`.

        :param guild_id: The guild to query.
        :param game: If given, restrict to this game identifier.
        :param day: If given, restrict to this date (YYYY-MM-DD).
        """
        from parsers.base import ScoreRecord  # avoid circular at module level

        conditions = ["guild_id = ?"]
        params: list = [str(guild_id)]
        if game:
            conditions.append("game = ?")
            params.append(game)
        if day:
            conditions.append("day = ?")
            params.append(day)

        where = " AND ".join(conditions)
        cursor = await self.connection.execute(
            f"SELECT user_id, user_name, game, day, score, meta "
            f"FROM user_scores WHERE {where} ORDER BY game, score",
            params,
        )
        rows = await cursor.fetchall()
        return [
            ScoreRecord(
                user_id=int(row[0]),
                user_name=row[1],
                game=row[2],
                day=row[3],
                score=row[4],
                meta=json.loads(row[5]) if row[5] else None,
            )
            for row in rows
        ]
