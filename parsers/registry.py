"""Auto-discovery of ScoreParser subclasses from the parsers/ package."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from functools import lru_cache
from pathlib import Path

from .base import ScoreParser

logger = logging.getLogger("trivial")

_PACKAGE_DIR = Path(__file__).resolve().parent
_PREFIX = f"{__package__}."


@lru_cache(maxsize=1)
def _parser_classes() -> tuple[type[ScoreParser], ...]:
    """Discover concrete parser classes (cached: module imports happen once)."""
    discovered: list[type[ScoreParser]] = []
    seen: set[str] = set()

    for _importer, modname, _ispkg in pkgutil.walk_packages(
        path=[str(_PACKAGE_DIR)], prefix=_PREFIX
    ):
        if modname in seen or modname == f"{_PREFIX}base":
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
                and getattr(obj, "game", "")  # skip helper/abstract bases
                and obj not in discovered
            ):
                discovered.append(obj)

    return tuple(discovered)


def discover_parsers() -> list[ScoreParser]:
    """Return a fresh instance of every concrete ``ScoreParser`` subclass."""
    return [cls() for cls in _parser_classes()]
