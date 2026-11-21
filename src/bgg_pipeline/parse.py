"""Pure XML -> dict parsing of BGG ``/thing`` responses (no I/O, easy to unit test).

BGG encodes "unknown" as ``0`` (year, weight, Bayesian average, player counts...).
Leaving those zeros in place would silently drag every average down, so they are
converted to ``None`` here: that is the single most important cleaning rule of the
project.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Any

from .schemas import LINK_TYPES

_NUM_RE = re.compile(r"\d+")


def _value(item: ET.Element, path: str) -> str | None:
    node = item.find(path)
    if node is None:
        return None
    value = node.attrib.get("value")
    return value.strip() if value is not None else None


def _int(raw: str | None, zero_is_null: bool = False) -> int | None:
    if raw in (None, "", "Not Ranked"):
        return None
    try:
        value = int(float(raw))
    except ValueError:
        return None
    return None if (zero_is_null and value == 0) else value


def _float(raw: str | None, zero_is_null: bool = False) -> float | None:
    if raw in (None, "", "Not Ranked"):
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return None if (zero_is_null and value == 0) else round(value, 5)


def _best_with(item: ET.Element) -> tuple[int | None, int | None]:
    """'Best with 3–4 players' -> (3, 4); '' or '(no votes)' -> (None, None)."""
    node = item.find("poll-summary/result[@name='bestwith']")
    numbers = [int(n) for n in _NUM_RE.findall(node.attrib.get("value", ""))] if node is not None else []
    if not numbers:
        return None, None
    return min(numbers), max(numbers)


def _description(item: ET.Element) -> str | None:
    text = item.findtext("description")
    if not text:
        return None
    # BGG double-escapes entities (&amp;mdash;) -> unescape once more, normalise whitespace.
    return re.sub(r"[ \t]+\n", "\n", html.unescape(text)).strip() or None


def parse_item(item: ET.Element) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    game_id = int(item.attrib["id"])
    primary = item.find("name[@type='primary']")
    best_min, best_max = _best_with(item)
    ratings = "statistics/ratings/"
    users_rated = _int(_value(item, ratings + "usersrated")) or 0
    num_weights = _int(_value(item, ratings + "numweights")) or 0

    record = {
        "game_id": game_id,
        "game_name": primary.attrib.get("value") if primary is not None else None,
        "year_published": _int(_value(item, "yearpublished"), zero_is_null=True),
        "min_players": _int(_value(item, "minplayers"), zero_is_null=True),
        "max_players": _int(_value(item, "maxplayers"), zero_is_null=True),
        "best_with_min": best_min,
        "best_with_max": best_max,
        "playing_time": _int(_value(item, "playingtime"), zero_is_null=True),
        "min_playtime": _int(_value(item, "minplaytime"), zero_is_null=True),
        "max_playtime": _int(_value(item, "maxplaytime"), zero_is_null=True),
        "min_age": _int(_value(item, "minage"), zero_is_null=True),
        "users_rated": users_rated,
        # An average over zero ratings is meaningless, not "0/10".
        "average_rating": _float(_value(item, ratings + "average"), zero_is_null=True)
        if users_rated
        else None,
        "bayes_average": _float(_value(item, ratings + "bayesaverage"), zero_is_null=True),
        "rating_stddev": _float(_value(item, ratings + "stddev")) if users_rated else None,
        "bgg_rank": _int(_value(item, ratings + "ranks/rank[@name='boardgame']")),
        "num_weights": num_weights,
        "weight_complexity": _float(_value(item, ratings + "averageweight"), zero_is_null=True)
        if num_weights
        else None,
        "owned": _int(_value(item, ratings + "owned")) or 0,
        "trading": _int(_value(item, ratings + "trading")) or 0,
        "wanting": _int(_value(item, ratings + "wanting")) or 0,
        "wishing": _int(_value(item, ratings + "wishing")) or 0,
        "num_comments": _int(_value(item, ratings + "numcomments")) or 0,
        "description": _description(item),
        "thumbnail_url": (item.findtext("thumbnail") or "").strip() or None,
        "image_url": (item.findtext("image") or "").strip() or None,
    }

    links = [
        {
            "game_id": game_id,
            "link_type": LINK_TYPES[link.attrib["type"]],
            "link_id": int(link.attrib["id"]),
            "link_name": html.unescape(link.attrib.get("value", "")).strip(),
        }
        for link in item.findall("link")
        if link.attrib.get("type") in LINK_TYPES
    ]
    return record, links


def parse_payload(payload: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse one raw ``/thing`` response into (game records, game links)."""
    root = ET.fromstring(payload)
    records, links = [], []
    for item in root.findall("item"):
        if item.attrib.get("type") != "boardgame":
            continue
        record, item_links = parse_item(item)
        records.append(record)
        links.extend(item_links)
    return records, links
