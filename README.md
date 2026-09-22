<p align="center">
  <img src="resources/triviala.png" alt="Trivial logo" width="150">
</p>

**trivial** is a Discord bot that automatically tracks game scores from chat
messages. When a user posts their daily score, trivial remembers the score. The `!scores` command can be used to display scores that trivial remembered.
Each day the bot can also post a reminder in the score channel: a list of the
supported games, yesterday's scoreboard, and every player who played yesterday
with their current streak of consecutive playing days.

# How to set up

1. Copy `.env.example` to `.env` and fill in your bot token and prefix:
   ```
   TOKEN=your-bot-token
   PREFIX=!
   ```
2. (Optional) Set the bot's target timezone so scores land on the right
   days — an IANA name like `America/New_York` or `Asia/Tokyo`:
   ```
   TIMEZONE=America/New_York
   ```
   When unset the bot uses UTC, which keeps every prior behaviour unchanged.
3. Install dependencies:
   ```
   python -m pip install -r requirements.txt
   ```
4. Run trivial:
   ```
   python bot.py
   ```

> **Required intents:** enable **Message Content Intent** (reads score
> messages) and **Server Members Intent** (resolves current server nicknames)
> under *Bot → Privileged Gateway Intents* in the [Discord Developer
> Portal](https://discord.com/developers/applications). Without the members
> intent, players the bot hasn't seen since its last restart may appear on
> leaderboards under the name they had when the score was recorded, and player nicknames may not be resolved correctly.

### Docker

```
docker compose up -d --build
```

### Deploy from GHCR

On a server with Docker:

```
GHCR_OWNER=your-github-user docker compose up -d
```

Make sure `.env` exists with at least `TOKEN` and `PREFIX`.

# Commands

| Command | Description |
|---------|-------------|
| `!/scores` | Today's scores across all games (available to everyone) |
| `!/scores wordle` | Today's Wordle scores (available to everyone) |
| `!/scores wordle 2026-09-17` | Wordle scores for a specific date (available to everyone) |
| `!/leaderboard` | Top 3 players for each game by average score, all time (available to everyone) |
| `!/leaderboard wordle` | Top 3 Wordle players by average score, all time (available to everyone) |
| `!/leaderboard wordle top` | Top 3 Wordle players by best single score, with the date of each best score (available to everyone) |
| `!/leaderboard wordle wins` | Top 3 Wordle players by number of first-place wins (available to everyone) |
| `!/leaderboard wordle count` | Top 3 Wordle players by number of games played (available to everyone) |
| `!/leaderboard wordle 2026-09-17` | Top 3 Wordle players for a specific date (available to everyone) |
| `!/leaderboard 2026-09-01 2026-09-21` | Top 3 players per game across a date range, e.g. a week (available to everyone) |
| `!/games` | List every supported game with a link to play (available to everyone) |
| `!/scorechannel set #channel` | Set the channel trivial monitors for scores (admins only) |
| `!/scorechannel remove` | Stop monitoring scores in this server (admins only) |
| `!/scorechannel show` | Show the currently monitored score channel (admins only) |
| `!/nuke confirm` | Permanently delete this server's recorded scores (admins only; keeps channel/reminder settings) |
| `!/backfill` | Scan the score channel's history and record score messages (admins only; `!/backfill 1000` scans more, `0` = all history) |
| `!/dailyreminder enable` | Enable the daily games reminder (admins only; posts to the score channel) |
| `!/dailyreminder disable` | Disable the daily games reminder (admins only) |
| `!/dailyreminder time 09:00` | Set the reminder time, 24-hour, in the bot's timezone (admins only) |
| `!/dailyreminder show` | Show the current reminder settings (admins only) |
| `!/dailyreminder test` | Preview the daily reminder (plus yesterday's scoreboard and players) in this channel (admins only) |
| `!/sync global` | Re-sync the slash command tree with Discord (bot owner only) |
| `!/unsync global` | Remove the bot's slash commands (bot owner only) |

Every command above works both as a slash command (`/scores`) and as a prefix command (`!scores`).

# Development notes


## Adding a new game

"Parsers" are used to extract the game's score from a message. Parsers are auto-discovered from the `parsers/` directory. Adding support for a new game is as simple as dropping in a new file that subclasses `ScoreParser`.

## Local testing

You can exercise the full parsing and score-recording pipeline without
deploying trivial:

```
# Single message
python local_tester.py -p "Wordle 1,234 4/6"

# Interactive REPL
python local_tester.py

# File of messages
python local_tester.py -f test_inputs.txt
```

Simulate different users with an `@Name:userid ::` prefix:

```
@Alice:1001 :: Wordle 1,234 4/6
@Bob:1002 :: Wordle 1,235 X/6
```

To also simulate a server nickname that differs from the user's global
name (the bot prefers the nickname everywhere — leaderboards, embeds):

```
@Captain:1001 :: Wordle 1,234 4/6                    # nickname == global name
@Captain~Alice:1001 :: Wordle 1,234 4/6              # nickname "Captain", global name "Alice"
```

Other flags:

```
python local_tester.py --list                          # Show discovered parsers
python local_tester.py --scores wordle --day 2026-09-17
python local_tester.py --leaderboard wordle            # Top-3-per-game leaderboard (all time)
python local_tester.py --leaderboard wordle --metric top  # Rank by best single score
python local_tester.py --leaderboard wordle --metric wins # Rank by first-place wins
python local_tester.py --leaderboard --day 2026-09-01 --end 2026-09-21
python local_tester.py -f inputs.txt --verbose
python local_tester.py -f inputs.txt --db out/test.db  # Custom DB path
```

## AI Disclosure
AI was used to generate the initial framework for this project, as well as some of the documentation. Only open-weight models were used for AI-generated content, run through open-source tooling.

## License

This project is licensed under the Apache License 2.0 — see [LICENSE.md](LICENSE.md)
for details.

## Credits

Built on the [Python Discord Bot Template](https://github.com/kkrypt0nn/Python-Discord-Bot-Template)
by [kkrypt0nn](https://github.com/kkrypt0nn).
