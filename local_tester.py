#!/usr/bin/env python3
"""
Lightweight local testing framework for scoreboard parsers.

Run parsers against text input without deploying the Discord bot, and
see exactly what would happen in production:

    1. select_parser  — decides which parser (game) handles the input
    2. parse          — the parser extracts the user's score
    3. record_score   — the score is logged to a local SQLite database
       (same schema + upsert logic the deployed bot uses)
    4. format_response— the embed is rendered as terminal text

Parsers are auto-discovered from the parsers/ package.

Usage:
    Interactive:  python local_tester.py
    Single input: python local_tester.py -p "Wordle 1,234 4/6"
    File mode:    python local_tester.py -f inputs.txt
    File (split): python local_tester.py -f multi.txt -d "---"

Flags:
    --list        Show discovered parsers and exit
    --verbose     Show dispatch decisions per parser
    --db PATH     Where to record scores (default: ./local_test.db)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
import discord

# ---------------------------------------------------------------------------
# Project root on sys.path so `parsers` / `database` import standalone
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from database import DatabaseManager  # noqa: E402
from parsers.base import ScoreParser, _utc_today  # noqa: E402
from parsers.dispatch import select_parser  # noqa: E402
from parsers.registry import discover_parsers  # noqa: E402
from parsers.scoring import build_scoreboard_embed  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# A line like "@Alice:1001 :: Wordle 1,234 4/6" lets test inputs come from
# a specific simulated user (name:id). The parser only ever sees the payload.
_AUTHOR_PREFIX = re.compile(
    r"^@(?P<name>[^:]+):(?P<uid>\d+)\s*::\s*(?P<content>.*)$"
)


def split_author(text: str) -> tuple[MockUser | None, str]:
    """If *text* starts with an author prefix, return (MockUser, payload)."""
    m = _AUTHOR_PREFIX.match(text)
    if m:
        return (
            MockUser(name=m.group("name"), uid=int(m.group("uid"))),
            m.group("content"),
        )
    return None, text

# ═══════════════════════════════════════════════════════════════════════════
# Mock Discord objects — lightweight stand-ins so parsers never need the bot
# ═══════════════════════════════════════════════════════════════════════════


class MockUser:
    """Stand-in for discord.Member / discord.User."""

    def __init__(self, name: str = "TestUser", uid: int = 1000) -> None:
        self.id = uid
        self.name = name
        self.display_name = name
        self.discriminator = "0000"
        self.bot = False
        self.mention = f"<@{uid}>"

    def __str__(self) -> str:
        return self.name


class MockChannel:
    """Stand-in for discord.TextChannel."""

    def __init__(self, name: str = "test-channel", cid: int = 2000) -> None:
        self.id = cid
        self.name = name

    def __str__(self) -> str:
        return f"#{self.name}"

    async def send(self, **kwargs: object) -> None:  # noqa: ARG002
        raise RuntimeError(
            "MockChannel.send() was called — parsers should return "
            "a ScoreResponse, not send messages directly."
        )


class MockGuild:
    """Stand-in for discord.Guild."""

    def __init__(self, name: str = "Test Server", gid: int = 3000) -> None:
        self.id = gid
        self.name = name

    def __str__(self) -> str:
        return self.name


class MockMessage:
    """Stand-in for discord.Message.

    Exposes the attributes that parsers are most likely to read.
    Extend this if a new parser touches more of the message API.
    """

    def __init__(
        self,
        content: str = "",
        author: MockUser | None = None,
        channel: MockChannel | None = None,
        guild: MockGuild | None = None,
        mid: int = 9999,
    ) -> None:
        self.content = content
        self.author = author or MockUser()
        self.channel = channel or MockChannel()
        self.guild = guild or MockGuild()
        self.id = mid
        self.created_at = datetime.now(timezone.utc)
        self.edited_at: datetime | None = None
        self.mentions: list[MockUser] = []
        self.mention_everyone = False
        self.attachments: list[object] = []
        self.embeds: list[discord.Embed] = []
        self.reactions: list[object] = []
        self.reference: object | None = None


# ═══════════════════════════════════════════════════════════════════════════
# Embed → terminal renderer
# ═══════════════════════════════════════════════════════════════════════════

_BAR = "─" * 54
_DBL  = "═" * 54


def _color_hex(c: discord.Colour | None) -> str:
    """Return a '#RRGGBB' string, or '(default)' if None/0."""
    if c is None:
        return "(default)"
    val = c.value
    return f"#{val:06X}"


def render_embed(embed: discord.Embed) -> str:
    """Turn a discord.Embed into a readable terminal representation."""
    parts: list[str] = [_DBL]

    # Title & URL
    if embed.title:
        parts.append(f"  {embed.title}")
    if embed.url:
        parts.append(f"  {embed.url}")

    # Description — keep line structure (leaderboards are multi-line)
    if embed.description:
        parts.append(_BAR)
        for line in embed.description.splitlines():
            parts.append(textwrap.indent(textwrap.fill(line, 50), "  "))

    # Author
    author = getattr(embed, "author", None)
    if author and getattr(author, "name", None):
        parts.append(_BAR)
        parts.append(f"  Author: {author.name}")
        if getattr(author, "url", None):
            parts.append(f"         {author.url}")

    # Color
    if embed.color and embed.color.value:
        parts.append(f"  Color: {_color_hex(embed.color)}")

    # Fields — keep line structure inside field values
    for field in embed.fields:
        parts.append(_BAR)
        tag = "  [inline]" if field.inline else ""
        parts.append(f"  {field.name}{tag}")
        val = field.value or "(empty)"
        for line in val.splitlines():
            parts.append(textwrap.indent(textwrap.fill(line, 48), "    "))

    # Footer
    footer_obj = getattr(embed, "footer", None)
    footer_text = getattr(footer_obj, "text", None) if footer_obj else None
    if footer_text:
        parts.append(_BAR)
        parts.append(f"  Footer: {footer_text}")

    # Image / Thumbnail
    img = getattr(embed, "image", None)
    if img and getattr(img, "url", None):
        parts.append(_BAR)
        parts.append(f"  Image: {img.url}")
    thumb = getattr(embed, "thumbnail", None)
    if thumb and getattr(thumb, "url", None):
        parts.append(_BAR)
        parts.append(f"  Thumbnail: {thumb.url}")

    parts.append(_DBL)
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# Parser pipeline — mirrors cogs/scoreboard.py exactly
# ═══════════════════════════════════════════════════════════════════════════


async def run_input(
    text: str,
    parsers: list[ScoreParser],
    db: DatabaseManager,
    verbose: bool = False,
) -> bool:
    """Feed *text* through the production pipeline. Returns True on a match.

    An optional ``@Name:id ::`` prefix on *text* simulates a different
    author so multi-user scenarios can be tested.
    """
    author, payload = split_author(text)
    msg = MockMessage(content=payload, author=author)

    # 1. Decide which parser handles this input
    parser = await select_parser(parsers, msg)
    if parser is None:
        if verbose:
            print("  → dispatch: no parser matched")
        return False

    # 2-4. Parse → record → format
    try:
        response = await parser.parse(msg)
        await parser.record_score(msg, response, db)

        player = response.username or msg.author.display_name
        score = "—" if response.score is None else response.score
        print(f"  Parsed by: {type(parser).__name__}  (game: '{parser.game}')")
        print(
            f"  → recorded {player} · {response.day} · "
            f"score={score}"
            f"{'  ·  ' + str(response.meta) if response.meta else ''}"
        )

        embed = await parser.format_response(response)
        print()
        print(render_embed(embed))
        return True
    except Exception as exc:
        print(f"  [!] {type(parser).__name__} raised {type(exc).__name__}: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Local database + input modes
# ═══════════════════════════════════════════════════════════════════════════


async def open_db(path: Path) -> DatabaseManager:
    """Open (creating if needed) the local score database."""
    connection = await aiosqlite.connect(str(path))
    schema = PROJECT_ROOT / "database" / "schema.sql"
    await connection.executescript(schema.read_text(encoding="utf-8"))
    await connection.commit()
    return DatabaseManager(connection=connection)


async def file_mode(
    path: str,
    parsers: list[ScoreParser],
    db: DatabaseManager,
    delimiter: str | None,
    verbose: bool,
) -> None:
    """Read inputs from *path* and run each through the pipeline."""
    p = Path(path)
    if not p.exists():
        print(f"Error: file not found: {path}")
        return

    raw = p.read_text(encoding="utf-8")

    if delimiter:
        inputs = [s.strip() for s in raw.split(delimiter) if s.strip()]
    else:
        inputs = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    if not inputs:
        print("No inputs found in file.")
        return

    print(f"Loaded {len(inputs)} input(s) from {path}\n")

    for i, text in enumerate(inputs, 1):
        print(f"── Input #{i} {'─' * 44}")
        print(f"  {text}")
        print()
        if not await run_input(text, parsers, db, verbose):
            print("  ⚠  No parser matched this input.")
        print()


async def interactive_mode(
    parsers: list[ScoreParser],
    db: DatabaseManager,
    verbose: bool,
) -> None:
    """REPL — type messages, see what the bot would post and record."""
    print()
    print("┌──────────────────────────────────────────────────────┐")
    print("│         Local Parser Tester  (interactive mode)      │")
    print("│  Type a message and press Enter to test parsing.     │")
    print("│  'list' to show parsers · 'quit' / Ctrl-D to exit.  │")
    print("└──────────────────────────────────────────────────────┘")
    print()

    while True:
        try:
            text = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not text:
            continue
        if text.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break
        if text.lower() == "list":
            print(f"  Registered parsers ({len(parsers)}):")
            for p in parsers:
                print(f"    • {type(p).__name__}  (game: '{p.game}')")
            print()
            continue

        if not await run_input(text, parsers, db, verbose):
            print("  ⚠  No parser matched this input.")
        print()


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════


def build_cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="local_tester",
        description="Test scoreboard parsers locally without deploying the bot.",
    )
    ap.add_argument(
        "-p", "--prompt",
        type=str,
        metavar="TEXT",
        default=None,
        help="Parse a single string and exit.",
    )
    ap.add_argument(
        "-f", "--file",
        type=str,
        metavar="PATH",
        default=None,
        help="Read inputs from a text file (one per line by default).",
    )
    ap.add_argument(
        "-d", "--delimiter",
        type=str,
        metavar="SEP",
        default=None,
        help="Split multi-message files on this exact line (e.g. '---').",
    )
    ap.add_argument(
        "--db",
        type=str,
        metavar="PATH",
        default="local_test.db",
        help="Where recorded scores are stored (default: ./local_test.db).",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Show which parsers were tried.",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        dest="list_parsers",
        help="List discovered parsers and exit.",
    )
    ap.add_argument(
        "--scores",
        nargs="?",
        const="",
        default=None,
        metavar="GAME",
        dest="scores_game",
        help="Show the leaderboard (same embed as !scores). Pass a game "
             "name to filter, or omit for all games.",
    )
    ap.add_argument(
        "--day",
        type=str,
        metavar="YYYY-MM-DD",
        default=None,
        help="Filter scores by date (used with --scores; default: today).",
    )
    return ap


async def amain(args: argparse.Namespace, parsers: list[ScoreParser]) -> None:
    db = await open_db(Path(args.db))
    try:
        print(f"Scores are recorded to: {args.db}\n")

        # ── Score leaderboard mode (mirrors !scores command) ──────────
        if args.scores_game is not None:
            game = args.scores_game or None  # "" → None (all games)
            day = args.day or _utc_today()
            records = await db.get_scores(guild_id=3000, game=game, day=day)
            sort_orders = {p.game: p.score_sort for p in parsers}
            embed = build_scoreboard_embed(
                records, game=game, day=day, sort_orders=sort_orders
            )
            print(render_embed(embed))
            return

        # ── Parse-input modes ─────────────────────────────────────────
        if args.prompt:
            text = args.prompt
            print(f"Input: {text}\n")
            if not await run_input(text, parsers, db, args.verbose):
                print("⚠  No parser matched this input.")
        elif args.file:
            await file_mode(args.file, parsers, db, args.delimiter, args.verbose)
        else:
            await interactive_mode(parsers, db, args.verbose)
    finally:
        await db.connection.close()


def main() -> None:
    args = build_cli().parse_args()

    # --- Discover parsers ---------------------------------------------------
    print("Discovering parsers …")
    parsers = discover_parsers()
    for p in parsers:
        print(f"  [+] {type(p).__name__}  (game: '{p.game}', sort: {p.score_sort})  ({type(p).__module__})")
    print(f"Found {len(parsers)} parser(s).\n")

    if args.list_parsers:
        for p in parsers:
            print(f"  • {type(p).__name__}  (game: '{p.game}')  ({type(p).__module__})")
        return

    asyncio.run(amain(args, parsers))


if __name__ == "__main__":
    main()