"""
Copyright © Krypton 2019-Present - https://github.com/kkrypt0nn (https://krypton.ninja)
Description:
🐍 A simple template to start to code your own and personalized Discord bot in Python

Version: 6.5.0
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import aiosqlite

if TYPE_CHECKING:
    from parsers.base import ScoreRecord


class DatabaseManager:
    def __init__(self, *, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    async def set_score_channel(self, server_id: int, channel_id: int) -> None:
        """Set the channel trivial monitors for scores in a server."""
        await self.connection.execute(
            "INSERT INTO score_channels(server_id, channel_id) VALUES (?, ?) "
            "ON CONFLICT(server_id) DO UPDATE SET channel_id=excluded.channel_id",
            (str(server_id), str(channel_id)),
        )
        await self.connection.commit()

    async def get_score_channel(self, server_id: int) -> int | None:
        """Get the channel trivial monitors for scores in a server."""
        rows = await self.connection.execute(
            "SELECT channel_id FROM score_channels WHERE server_id=?",
            (str(server_id),),
        )
        async with rows as cursor:
            result = await cursor.fetchone()
            return int(result[0]) if result is not None else None

    async def remove_score_channel(self, server_id: int) -> None:
        """Remove the monitored score channel from a server."""
        await self.connection.execute(
            "DELETE FROM score_channels WHERE server_id=?",
            (str(server_id),),
        )
        await self.connection.commit()

    async def set_daily_reminder(
        self,
        server_id: int,
        enabled: bool,
        reminder_time: str,
    ) -> None:
        """Upsert the daily reminder settings for a server."""
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
        """Get the daily reminder settings for a server, or None if unset."""
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
        """Record that the daily reminder was sent for *day* so it doesn't re-fire."""
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
        score: int | float | None,
        meta: dict[str, str] | None = None,
    ) -> None:
        """Log one user's score for one game on one day."""
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

    async def delete_guild_scores(self, guild_id: int) -> int:
        """Delete every recorded score for the given guild."""
        cursor = await self.connection.execute(
            "DELETE FROM user_scores WHERE guild_id = ?", (str(guild_id),)
        )
        await self.connection.commit()
        return cursor.rowcount

    async def get_play_days(self, guild_id: int) -> list[tuple[int, str, str]]:
        """Fetch one row per (user, day) a score was recorded for a guild."""
        cursor = await self.connection.execute(
            "SELECT user_id, MAX(user_name), day FROM user_scores "
            "WHERE guild_id = ? GROUP BY user_id, day ORDER BY day, user_id",
            (str(guild_id),),
        )
        rows = await cursor.fetchall()
        return [(int(row[0]), row[1], row[2]) for row in rows]

    async def get_scores(
        self,
        guild_id: int,
        game: str | None = None,
        day: str | None = None,
        end_day: str | None = None,
    ) -> list[ScoreRecord]:
        """Fetch leaderboard rows for a guild, optionally filtered by game and/or date."""
        from parsers.base import ScoreRecord  # avoid circular at module level

        conditions = ["guild_id = ?"]
        params: list[str] = [str(guild_id)]
        if game:
            conditions.append("game = ?")
            params.append(game)
        if day and end_day:
            conditions.append("day BETWEEN ? AND ?")
            params.extend([day, end_day])
        elif day or end_day:
            conditions.append("day = ?")
            params.append(day or end_day)

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
