"""Auto-discovery of ScoreParser subclasses from the parsers/ package.

Both the deployed cog and the local tester use this, so adding a parser is a
single action: drop a ``.py`` file into ``parsers/`` that defines a
``ScoreParser`` subclass with a ``game`` identifier.  No registration edits
needed anywhere.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil

import parsers as parsers_pkg

from .base import ScoreParser

logger = logging.getLogger("discord_bot")


def discover_parsers() -> list[ScoreParser]:
    """Return every concrete ``ScoreParser`` subclass found in this package.

    Rules:

    - Classes that don't declare a ``game`` identifier are treated as
      abstract helpers and skipped.
    - Only classes *defined in* the scanned module are picked up, so
      re-exported/inherited classes aren't registered twice.
    """
    discovered: list[ScoreParser] = []
    seen: set[str] = set()
    prefix = f"{parsers_pkg.__name__}."  # e.g. "parsers."

    for _importer, modname, _ispkg in pkgutil.walk_packages(
        path=list(parsers_pkg.__path__), prefix=prefix
    ):
        if modname in seen or modname in (
            parsers_pkg.__name__,
            f"{parsers_pkg.__name__}.__init__",
            f"{parsers_pkg.__name__}.base",
        ):
            continue
        seen.add(modname)

        try:
            mod = importlib.import_module(modname)
        except Exception:
            logger.exception("Could not import parser module %s", modname)
            continue

        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, ScoreParser)
                and obj is not ScoreParser
                and getattr(obj, "__module__", "") == modname  # defined here
            ):
                instance = obj()
                if not getattr(instance, "game", ""):
                    continue  # helper/abstract base without a game id
                discovered.append(instance)

    return discovered