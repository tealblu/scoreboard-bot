# Trivial

**trivial** is a Discord bot that automatically tracks game scores from chat
messages. When a user posts a score (e.g. a Wordle result), trivial parses it,
stores it in SQLite, and replies with a formatted embed. A `!scores` command
retrieves leaderboards filtered by game and date.

Parsers are auto-discovered from the `parsers/` directory — adding support for
a new game is as simple as dropping in a new file that subclasses `ScoreParser`.

## How to set up

1. Copy `.env.example` to `.env` and fill in your bot token and prefix:
   ```
   TOKEN=your-bot-token
   PREFIX=!
   ```
2. Install dependencies:
   ```
   python -m pip install -r requirements.txt
   ```
3. Run trivial:
   ```
   python bot.py
   ```

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

## Commands

| Command | Description |
|---------|-------------|
| `!scores` | Today's scores across all games |
| `!scores wordle` | Today's Wordle scores |
| `!scores wordle 2026-09-17` | Wordle scores for a specific date |
| `!/nuke confirm` | Permanently delete this server's recorded scores (admins only; keeps channel/reminder settings) |
| `!/backfill` | Scan the score channel's history and record score messages (admins only; `!/backfill 1000` scans more, `0` = all history) |
| `!/dailyreminder enable` | Enable the daily games reminder (posts to the score channel) |
| `!/dailyreminder disable` | Disable the daily games reminder |
| `!/dailyreminder time 09:00` | Set the reminder time (UTC, 24-hour) |
| `!/dailyreminder show` | Show the current reminder settings |
| `!/dailyreminder test` | Preview the daily reminder (plus yesterday's scoreboard) in this channel |

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

Other flags:

```
python local_tester.py --list                          # Show discovered parsers
python local_tester.py --scores wordle --day 2026-09-17
python local_tester.py -f inputs.txt --verbose
python local_tester.py -f inputs.txt --db out/test.db  # Custom DB path
```

## License

This project is licensed under the Apache License 2.0 — see [LICENSE.md](LICENSE.md)
for details.

## Credits

Built on the [Python Discord Bot Template](https://github.com/kkrypt0nn/Python-Discord-Bot-Template)
by [kkrypt0nn](https://github.com/kkrypt0nn).
