# Python Discord Bot Template

<p align="center">
  <a href="https://discord.gg/xj6y5ZaTMr"><img src="https://img.shields.io/discord/1358456011316396295?logo=discord"></a>
  <a href="https://github.com/kkrypt0nn/Python-Discord-Bot-Template/releases"><img src="https://img.shields.io/github/v/release/kkrypt0nn/Python-Discord-Bot-Template"></a>
  <a href="https://github.com/kkrypt0nn/Python-Discord-Bot-Template/commits/main"><img src="https://img.shields.io/github/last-commit/kkrypt0nn/Python-Discord-Bot-Template"></a>
  <a href="https://github.com/kkrypt0nn/Python-Discord-Bot-Template/blob/main/LICENSE.md"><img src="https://img.shields.io/github/license/kkrypt0nn/Python-Discord-Bot-Template"></a>
  <a href="https://github.com/kkrypt0nn/Python-Discord-Bot-Template"><img src="https://img.shields.io/github/languages/code-size/kkrypt0nn/Python-Discord-Bot-Template"></a>
  <a href="https://conventionalcommits.org/en/v1.0.0/"><img src="https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196?logo=conventionalcommits&logoColor=white"></a>
  <a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

> [!NOTE]
> This project is in a **feature-freeze mode**, please read more about it [here](https://github.com/kkrypt0nn/Python-Discord-Bot-Template/issues/112). It can be summed up in a few bullet points:
> 
> * The project **will** receive bug fixes
> * The project **will** be updated to make sure it works with the **latest** discord.py version
> * The project **will not** receive any new features, **unless one of the following applies**:
>   * A new feature is added to Discord and it would be beneficial to have it in the template
>   * A feature got a breaking change, this fits with the same point that the project will **always** support the latest discord.py version

This repository is a template that everyone can use for the start of their Discord bot.

When I first started creating my Discord bot it took me a while to get everything setup and working with cogs and more.
I would've been happy if there were any template existing. However, there wasn't any existing template. That's why I
decided to create my own template to let **you** guys create your Discord bot easily.

Please note that this template is not supposed to be the best template, but a good template to start learning how
discord.py works and to make your own bot easily.

If you plan to use this template to make your own template or bot, you **have to**:

- Keep the credits, and a link to this repository in all the files that contains my code
- Keep the same license for unchanged code

See [the license file](https://github.com/kkrypt0nn/Python-Discord-Bot-Template/blob/master/LICENSE.md) for more
information, I reserve the right to take down any repository that does not meet these requirements.

## Support

Before requesting support, you should know that this template requires you to have at least a **basic knowledge** of
Python and the library is made for **advanced users**. Do not use this template if you don't know the
basics or some advanced topics such as OOP or async. [Here's](https://pythondiscord.com/pages/resources) a link for resources to learn python.

If you need some help for something, do not hesitate to create an issue over [here](https://github.com/kkrypt0nn/Python-Discord-Bot-Template/issues), but don't forget the read the [frequently asked questions](https://github.com/kkrypt0nn/Python-Discord-Bot-Template/wiki/Frequently-Asked-Questions) before.

All the updates of the template are available [here](UPDATES.md).

## Disclaimer

Slash commands can take some time to get registered globally, so if you want to test a command you should use
the `@app_commands.guilds()` decorator so that it gets registered instantly. Example:

```py
@commands.hybrid_command(
  name="command",
  description="Command description",
)
@app_commands.guilds(discord.Object(id=GUILD_ID)) # Place your guild ID here
```

When using the template you confirm that you have read the [license](LICENSE.md) and comprehend that I can take down
your repository if you do not meet these requirements.

## How to download it

This repository is now a template, on the top left you can simply click on "**Use this template**" to create a GitHub
repository based on this template.

Alternatively you can do the following:

- Clone/Download the repository
  - To clone it and get the updates you can definitely use the command
    `git clone`
- Create a Discord bot [here](https://discord.com/developers/applications)
- Get your bot token
- Invite your bot on servers using the following invite:
  https://discord.com/oauth2/authorize?&client_id=YOUR_APPLICATION_ID_HERE&scope=bot+applications.commands&permissions=PERMISSIONS (
  Replace `YOUR_APPLICATION_ID_HERE` with the application ID and replace `PERMISSIONS` with the required permissions
  your bot needs that it can be get at the bottom of a this
  page https://discord.com/developers/applications/YOUR_APPLICATION_ID_HERE/bot)

## How to set up

To set up the token you will have to make use of the [`.env.example`](.env.example) file; you should rename it to `.env` and replace the `YOUR_BOT...` content with your actual values that match for your bot.

Alternatively you can simply create a system environment variable with the same names and their respective value.

## How to start

### The _"usual"_ way

To start the bot you simply need to launch, either your terminal (Linux, Mac & Windows), or your Command Prompt (
Windows)
.

Before running the bot you will need to install all the requirements with this command:

```
python -m pip install -r requirements.txt
```

After that you can start it with

```
python bot.py
```

> **Note**: You may need to replace `python` with `py`, `python3`, `python3.11`, etc. depending on what Python versions you have installed on the machine.

### Docker

Support to start the bot in a Docker container has been added. After having [Docker](https://docker.com) installed on your machine, you can simply execute:

```
docker compose up -d --build
```

> **Note**: `-d` will make the container run in detached mode, so in the background.

### Deploy from GHCR (production)

The bot image is published to **GitHub Container Registry** automatically by the
`Publish Docker image` workflow (on every push to `main` and on `v*` tags).

On a server with Docker installed:

1. Set the owner in the compose file (use your GitHub username or organization, or set a `GHCR_OWNER` env var):

   ```
   GHCR_OWNER=your-github-user docker compose up -d
   ```

2. Make sure `.env` exists next to `docker-compose.yml` with at least `TOKEN`, `PREFIX` and `INVITE_LINK` set.

The database and log file live in the `bot-data` Docker volume (survives
container updates/restarts).

> **Note**: GHCR packages are **private by default**. Open the package settings
> (https://github.com/users/<owner>/packages/container/package/scoreboard-bot) and
> set visibility to **Public** if you want to pull the image without authentication.

## Local parser testing

You can exercise the **full score-recording pipeline** without deploying the bot
or needing a Discord token:

```
1. select_parser   → decides which parser (game) handles the input
2. parse           → the parser extracts the user's score
3. record_score    → the score is written to a local SQLite DB
4. format_response → the embed is rendered as terminal text
```

Parser classes are auto-discovered from the `parsers/` directory — just drop in a
file that subclasses `ScoreParser` (one parser per game: Wordle gets a parser,
MapTap gets a parser, etc.), give it a unique `game` identifier (and optionally
`score_sort = "desc"` if lower isn't better), and it is picked up by **both**
the local tester and the deployed cog — no registration edits anywhere.

Scores are stored per row `(guild, user, game, day)`, so many users can post many
games and re-posting the same daily score simply overwrites that day's row.

Prerequisite: install the requirements in a virtual environment:

```
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Run it with one of three input modes:

```
# 1. Single prompt — parse one string and show what the bot would post
python local_tester.py -p "Wordle 1,234 4/6"

# 2. Interactive REPL — type messages one at a time
python local_tester.py

# 3. File — one message per line
python local_tester.py -f test_inputs.txt

# 3b. File with a delimiter line (e.g. '---') for multi-line messages
python local_tester.py -f test_inputs.txt -d "---"
```

Simulate different users by prefixing an input with `@Name:userid ::` — the
prefix is stripped before parsing, and the score is recorded for that user:

```
# test_inputs.txt
@Alice:1001 :: Wordle 1,234 4/6
@Bob:1002 :: Wordle 1,235 X/6
@Alice:1001 :: Wordle 1,234 5/6   # same day → overwrites Alice's row (upsert)
```

Other flags:

```
python local_tester.py --list                 # Show discovered parsers
python local_tester.py -f inputs.txt --verbose
python local_tester.py -f inputs.txt --db out/test.db   # where scores are stored
```

**Reading scores back** — the tester's `--scores` mode uses the **exact same
core code** as the bot's `!scores` command (`DatabaseManager.get_scores` +
`parsers.scoring.build_scoreboard_embed`), so you can preview the leaderboard
embed before deploying:

```
python local_tester.py --scores                    # today, all games
python local_tester.py --scores wordle             # today, wordle only
python local_tester.py --scores wordle --day 2026-09-17   # specific date
```

Since `get_scores` ties rows to a guild, the local query uses the mock
guild id (3000), matching where the tester records scores.

Notes:

- Parsers never hit the network: messages are mocked, and the resulting
  `discord.Embed` is rendered as terminal text, so you can review exactly what
  would be sent to the channel.
- A parser whose `format_response` builds a `discord.Embed` must `import discord`
  at module level (not only under `TYPE_CHECKING`), since the embed is constructed
  at runtime.
- Parser classes without a `game` identifier are treated as helpers and skipped
  during auto-discovery.

## `!scores` command

The deployed bot has a prefix command that queries the same underlying data:

```
!scores                    — today's scores, all games
!scores wordle             — today's wordle scores
!scores wordle 2026-09-17  — wordle scores for a specific date
```

Command → data flow (shared with the local tester):

```
!scores  ──┐
           ├─→  DatabaseManager.get_scores(guild_id, game, day)
--scores ──┘              │
                          ▼
              parsers.scoring.build_scoreboard_embed(records)
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        Discord embed         terminal render
        (channel reply)        (local tester)
```

## Issues or Questions

If you have any issues or questions of how to code a specific command, you can:

- Join my Discord server [here](https://discord.gg/xj6y5ZaTMr)
- Post them [here](https://github.com/kkrypt0nn/Python-Discord-Bot-Template/issues)

Me or other people will take their time to answer and help you.

## Versioning

We use [SemVer](http://semver.org) for versioning. For the versions available, see
the [tags on this repository](https://github.com/kkrypt0nn/Python-Discord-Bot-Template/tags).

## Built With

- [Python 3.12.12](https://www.python.org/)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE.md](LICENSE.md) file for details
