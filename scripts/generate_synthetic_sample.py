"""Generate the synthetic, BGG-shaped Bronze sample committed in ``sample_data/``.

Why synthetic? The BGG XML API licence is non-commercial and does not cover
redistributing its data, so the public repository ships invented games instead. The
payloads mimic the exact XML of ``/xmlapi2/thing?stats=1`` (names, links, polls,
statistics...), so the whole pipeline - parsing included - runs offline on them.

Real results quoted in the README come from real API data kept locally (``local_data/``).

What the generator models:
* 6 archetypes (party, family, strategy, expert, wargame, solo puzzle) with their own
  weight, duration, player counts, mechanics and themes;
* market trends: more solo & cooperative games and fewer roll-and-move games over time;
* ratings that grow with complexity, popularity following a power law;
* 4 weekly snapshots (ratings accumulate, ranks move) to exercise the history fact;
* deliberate data-quality traps: BGG "0 = unknown" values, min > max players,
  60-hour wargames, games announced for next year.

    python scripts/generate_synthetic_sample.py --games 2500 --seed 7
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bgg_pipeline.extract import BRONZE_SCHEMA  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "sample_data" / "bronze" / "synthetic_bgg_thing.parquet"
FIRST_SNAPSHOT = datetime(2026, 10, 26, 6, 0, tzinfo=UTC)
N_SNAPSHOTS = 4
BATCH = 20

MECHANICS = {
    2001: "Action Points",
    2002: "Tile Placement",
    2004: "Set Collection",
    2008: "Trading",
    2011: "Modular Board",
    2012: "Auction / Bidding",
    2015: "Variable Player Powers",
    2017: "Voting",
    2019: "Team-Based Game",
    2020: "Simultaneous Action Selection",
    2023: "Cooperative Game",
    2026: "Hexagon Grid",
    2027: "Storytelling",
    2028: "Role Playing",
    2035: "Roll / Spin and Move",
    2040: "Hand Management",
    2041: "Open Drafting",
    2046: "Area Movement",
    2048: "Pattern Building",
    2072: "Dice Rolling",
    2073: "Acting",
    2080: "Area Majority / Influence",
    2082: "Worker Placement",
    2664: "Deck, Bag, and Pool Building",
    2685: "Player Elimination",
    2686: "Take That",
    2689: "Real-Time",
    2810: "Push Your Luck",
    2819: "Solo / Solitaire Game",
    2822: "Scenario / Mission / Campaign Game",
    2853: "Narrative Choice / Paragraph",
    2875: "End Game Bonuses",
    2897: "Variable Set-up",
    2984: "Drafting",
    2991: "Line of Sight",
}
CATEGORIES = {
    1002: "Card Game",
    1009: "Abstract Strategy",
    1010: "Fantasy",
    1013: "Farming",
    1015: "Civilization",
    1016: "Science Fiction",
    1017: "Dice",
    1019: "Wargame",
    1020: "Exploration",
    1021: "Economic",
    1024: "Horror",
    1026: "Negotiation",
    1028: "Puzzle",
    1030: "Party Game",
    1039: "Deduction",
    1041: "Children's Game",
    1044: "Medieval",
    1046: "Fighting",
    1047: "Miniatures",
    1048: "Ancient",
    1049: "World War II",
    1064: "Movies / TV / Radio theme",
    1082: "Mythology",
    1084: "Environmental",
    1089: "Animals",
    1094: "Educational",
    1097: "Adventure",
}

# archetype: (share, weight mean/sd, durations, (min_p, max_p) choices, mechanics, categories)
ARCHETYPES = {
    "party": (
        0.18,
        1.25,
        0.2,
        [15, 20, 30, 45],
        [(3, 8), (3, 10), (4, 12), (2, 8)],
        [2017, 2073, 2019, 2689, 2686, 2810, 2040],
        [1030, 1002, 1039, 1064, 1089],
    ),
    "family": (
        0.30,
        1.75,
        0.3,
        [30, 40, 45, 60],
        [(2, 4), (2, 5), (1, 4), (2, 6)],
        [2004, 2002, 2048, 2041, 2072, 2810, 2035, 2008, 2040],
        [1002, 1089, 1013, 1017, 1041, 1084],
    ),
    "strategy": (
        0.25,
        2.6,
        0.35,
        [60, 75, 90, 120],
        [(2, 4), (1, 4), (2, 5), (1, 5)],
        [2082, 2040, 2875, 2015, 2664, 2004, 2080, 2041, 2897, 2001, 2023, 2011],
        [1021, 1015, 1016, 1010, 1044, 1013, 1048, 1084],
    ),
    "expert": (
        0.12,
        3.6,
        0.4,
        [120, 150, 180, 240],
        [(1, 4), (2, 4), (1, 5)],
        [2082, 2001, 2875, 2015, 2897, 2080, 2822, 2664, 2011],
        [1021, 1015, 1016, 1048, 1044, 1020],
    ),
    "wargame": (
        0.09,
        3.3,
        0.5,
        [120, 180, 240, 360, 600],
        [(2, 2), (1, 2), (2, 4)],
        [2072, 2026, 2991, 2046, 2822, 2020, 2685],
        [1019, 1049, 1048, 1047, 1046],
    ),
    "adventure": (
        0.06,
        2.5,
        0.4,
        [60, 90, 120],
        [(1, 4), (1, 2), (1, 1)],
        [2819, 2023, 2822, 2853, 2027, 2028, 2664, 2072],
        [1097, 1020, 1010, 1024, 1082, 1016],
    ),
}

ADJ = [
    "Crimson",
    "Silent",
    "Golden",
    "Hidden",
    "Iron",
    "Lost",
    "Wild",
    "Ancient",
    "Northern",
    "Clockwork",
    "Emerald",
    "Sunken",
    "Burning",
    "Frozen",
    "Velvet",
    "Hollow",
    "Radiant",
    "Shattered",
    "Twilight",
    "Copper",
    "Gilded",
    "Misty",
    "Electric",
    "Royal",
    "Feral",
    "Lunar",
    "Painted",
    "Restless",
]
NOUN = [
    "Harbor",
    "Lantern",
    "Kingdom",
    "Orchard",
    "Citadel",
    "Expedition",
    "Bazaar",
    "Frontier",
    "Garden",
    "Labyrinth",
    "Caravan",
    "Observatory",
    "Archipelago",
    "Monastery",
    "Railway",
    "Workshop",
    "Canyon",
    "Dynasty",
    "Festival",
    "Reef",
    "Tavern",
    "Foundry",
    "Galaxy",
    "Meadow",
    "Pyramid",
    "Outpost",
]
FIRST = [
    "Alex",
    "Bruno",
    "Chloé",
    "Dana",
    "Elias",
    "Fatou",
    "Greta",
    "Hiro",
    "Inès",
    "Jonas",
    "Kira",
    "Luca",
    "Maya",
    "Nils",
    "Olga",
    "Paolo",
    "Quentin",
    "Rosa",
    "Samir",
    "Tess",
    "Ugo",
    "Vera",
]
LAST = [
    "Arden",
    "Bellamy",
    "Castell",
    "Dorsey",
    "Ekberg",
    "Fontaine",
    "Garnier",
    "Holt",
    "Ivers",
    "Jansen",
    "Keller",
    "Lemaire",
    "Moreau",
    "Novak",
    "Okafor",
    "Petit",
    "Rossi",
    "Sato",
    "Varga",
]
PUB_A = ["Blue", "Little", "Red", "Happy", "Grey", "Tiny", "Lucky", "Bold", "Quiet", "Bright"]
PUB_B = ["Owl", "Meeple", "Fox", "Dragon", "Pawn", "Cube", "Lantern", "Badger", "Comet", "Anvil"]
PUB_C = ["Games", "Studio", "Editions", "Publishing", "Workshop"]


def fake_people(rng: np.random.Generator, n: int, start_id: int) -> dict[int, str]:
    names = {f"{first} {last}" for first in FIRST for last in LAST}
    chosen = rng.choice(sorted(names), size=min(n, len(names)), replace=False)
    return {start_id + i: str(name) for i, name in enumerate(chosen)}


def fake_publishers(rng: np.random.Generator, n: int) -> dict[int, str]:
    names = sorted({f"{a} {b} {c}" for a in PUB_A for b in PUB_B for c in PUB_C})
    chosen = rng.choice(names, size=n, replace=False)
    pubs = {30_000 + i: str(name) for i, name in enumerate(chosen)}
    pubs[4] = "(Self-Published)"
    return pubs


def make_games(n: int, rng: np.random.Generator) -> list[dict]:
    ids = rng.choice(np.arange(1, 485_001), size=n, replace=False)
    designers = fake_people(rng, 350, 10_000)
    publishers = fake_publishers(rng, 120)
    pub_ids = [p for p in publishers if p != 4]
    pub_popularity = rng.pareto(1.2, len(pub_ids)) + 1
    pub_p = pub_popularity / pub_popularity.sum()
    kinds = list(ARCHETYPES)
    shares = np.array([ARCHETYPES[k][0] for k in kinds])
    used_names: set[str] = set()
    games = []
    for gid in ids:
        kind = kinds[rng.choice(len(kinds), p=shares / shares.sum())]
        _, w_mu, w_sd, durations, players, mech_pool, cat_pool = ARCHETYPES[kind]

        # Publication year: growing market, a few unknown (0) and announced (next year).
        u = rng.random()
        if u < 0.03:
            year = 0
        elif u < 0.045:
            year = 2027
        elif u < 0.15:
            year = int(rng.integers(1950, 1995))
        else:
            year = int(2026 - min(31, rng.exponential(8)))
        recent = max(0.0, (year - 2000) / 26) if year else 0.3

        weight = float(np.clip(rng.normal(w_mu, w_sd), 1.0, 4.9))
        min_p, max_p = players[rng.integers(len(players))]
        playing_time = int(rng.choice(durations))

        # Trends: solo & coop up, roll-and-move down.
        mechs = set(rng.choice(mech_pool, size=min(len(mech_pool), int(rng.integers(2, 5))), replace=False))
        if rng.random() < 0.05 + 0.35 * recent * (kind in ("strategy", "expert", "adventure")):
            mechs.add(2819)
            min_p = 1
        if rng.random() < 0.04 + 0.2 * recent:
            mechs.add(2023)
        if kind == "family" and rng.random() < 0.5 * (1 - recent):
            mechs.add(2035)
        elif 2035 in mechs and rng.random() < recent:
            mechs.discard(2035)
        cats = set(rng.choice(cat_pool, size=int(rng.integers(1, 3)), replace=False))

        # Popularity (power law, older & better games accumulate more ratings).
        base = rng.lognormal(mean=2.6 + 1.2 * (kind != "party"), sigma=1.7)
        users_rated = int(base * (1.3 if year and year < 2015 else 1.0))
        if year == 2027:
            users_rated = int(rng.integers(0, 40))
        quality = (
            5.4
            + 0.55 * (weight - 1)
            + 0.8 * recent
            + 0.5 * (2822 in mechs)
            + 0.3 * (2819 in mechs)
            - 0.9 * (2035 in mechs)
            + rng.normal(0, 0.55)
        )

        name = f"{rng.choice(ADJ)} {rng.choice(NOUN)}"
        while name in used_names:
            name = f"{rng.choice(ADJ)} {rng.choice(NOUN)}: {rng.choice(NOUN)}"
        used_names.add(name)

        n_designers = int(rng.integers(1, 3))
        game = {
            "id": int(gid),
            "name": name,
            "kind": kind,
            "year": year,
            "min_players": min_p,
            "max_players": max_p,
            "playing_time": playing_time,
            "min_age": int(rng.choice([6, 8, 10, 12, 14])),
            "weight": weight,
            "quality": float(np.clip(quality, 2.0, 9.4)),
            "users_rated": users_rated,
            "owned_ratio": float(rng.uniform(1.8, 4.0)),
            "wish_ratio": float(rng.lognormal(np.log(0.12 + 0.25 * recent), 0.5)),
            "mechanics": sorted(mechs),
            "categories": sorted(cats),
            "designers": [int(d) for d in rng.choice(list(designers), size=n_designers, replace=False)],
            "publishers": [4] if rng.random() < 0.08 else [int(rng.choice(pub_ids, p=pub_p))],
        }
        games.append(game)

    # Deliberate data-quality traps (all legitimate on the real BGG).
    games[0]["min_players"], games[0]["max_players"] = 4, 2
    for g in games[1:3]:
        g.update(kind="wargame", playing_time=3600, weight=4.6)
    games[3]["playing_time"] = 0  # BGG "unknown"
    games[4]["users_rated"] = 0
    return games, designers, publishers


def item_xml(g: dict, week: int, rng: np.random.Generator, designers, publishers, ranks) -> str:
    growth = 1 + week * (0.01 + 0.05 * (g["year"] >= 2025))
    users = int(g["users_rated"] * growth)
    avg = (
        float(np.clip(g["quality"] + rng.normal(0, 0.6 / np.sqrt(users + 1)) + 0.02 * week, 1, 10))
        if users
        else 0
    )
    weights = int(users * 0.08)
    owned = int(users * g["owned_ratio"]) + int(rng.integers(0, 4))
    wishing = int(owned * g["wish_ratio"]) + (int(users * 8) if g["year"] == 2027 else 0)
    bayes = (users * avg + 1500 * 5.5) / (users + 1500) if users >= 30 else 0
    rank = ranks.get(g["id"], "Not Ranked")
    links = (
        [("boardgamemechanic", m, MECHANICS[m]) for m in g["mechanics"]]
        + [("boardgamecategory", c, CATEGORIES[c]) for c in g["categories"]]
        + [("boardgamedesigner", d, designers[d]) for d in g["designers"]]
        + [("boardgamepublisher", p, publishers[p]) for p in g["publishers"]]
    )
    link_xml = "\n".join(f'    <link type="{t}" id="{i}" value={quoteattr(v)} />' for t, i, v in links)
    best = (
        f"Best with {g['min_players']}"
        if g["max_players"] == g["min_players"]
        else (f"Best with {min(g['max_players'], g['min_players'] + 1)} players")
    )
    desc = escape(
        f"{g['name']} is a {g['kind']} game for {g['min_players']}-{g['max_players']} players. "
        "Synthetic demo data generated for the BGG pipeline portfolio project."
    )
    return f"""  <item type="boardgame" id="{g["id"]}">
    <name type="primary" sortindex="1" value={quoteattr(g["name"])} />
    <description>{desc}</description>
    <yearpublished value="{g["year"]}" />
    <minplayers value="{g["min_players"]}" />
    <maxplayers value="{g["max_players"]}" />
    <poll-summary name="suggested_numplayers" title="User Suggested Number of Players">
      <result name="bestwith" value="{best}" />
    </poll-summary>
    <playingtime value="{g["playing_time"]}" />
    <minplaytime value="{max(0, g["playing_time"] - 15) if g["playing_time"] else 0}" />
    <maxplaytime value="{g["playing_time"]}" />
    <minage value="{g["min_age"]}" />
{link_xml}
    <statistics page="1">
      <ratings>
        <usersrated value="{users}" />
        <average value="{avg:.5f}" />
        <bayesaverage value="{bayes:.5f}" />
        <ranks>
          <rank type="subtype" id="1" name="boardgame" friendlyname="Board Game Rank" value="{rank}" />
        </ranks>
        <stddev value="{1.1 + rng.random():.5f}" />
        <owned value="{owned}" />
        <trading value="{int(owned * 0.02)}" />
        <wanting value="{int(wishing * 0.1)}" />
        <wishing value="{wishing}" />
        <numcomments value="{int(users * 0.25)}" />
        <numweights value="{weights}" />
        <averageweight value="{g["weight"] if weights else 0:.4f}" />
      </ratings>
    </statistics>
  </item>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=2500)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    games, designers, publishers = make_games(args.games, rng)

    rows = []
    for week in range(N_SNAPSHOTS):
        fetched_at = FIRST_SNAPSHOT + timedelta(days=7 * week)
        run_id = f"synthetic_run_{fetched_at:%Y%m%d}"
        # Rank = position by Bayesian average among ranked games, scaled to BGG magnitudes.
        scored = sorted(
            (g for g in games if g["users_rated"] >= 30 and g["year"] != 2027),
            key=lambda g: (
                -(g["quality"] * g["users_rated"] * (1 + 0.03 * week * (g["year"] >= 2024)) + 5.5 * 1500)
                / (g["users_rated"] + 1500)
            ),
        )
        ranks = {g["id"]: (i + 1) * 9 for i, g in enumerate(scored)}
        for batch_no, start in enumerate(range(0, len(games), BATCH), start=1):
            batch = games[start : start + BATCH]
            items = "\n".join(item_xml(g, week, rng, designers, publishers, ranks) for g in batch)
            payload = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<items termsofuse="https://boardgamegeek.com/xmlapi/termsofuse">\n'
                f"{items}\n</items>"
            )
            ids = [g["id"] for g in batch]
            rows.append(
                {
                    "run_id": run_id,
                    "batch_no": batch_no,
                    "requested_ids": ids,
                    "source_url": "synthetic://xmlapi2/thing?stats=1&id=" + ",".join(map(str, ids)),
                    "http_status": 200,
                    "fetched_at": fetched_at + timedelta(seconds=2 * batch_no),
                    "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
                    "payload": payload,
                }
            )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.Table.from_pylist(rows, schema=BRONZE_SCHEMA), OUT, compression="zstd", compression_level=19
    )
    print(
        f"{len(games)} synthetic games x {N_SNAPSHOTS} snapshots -> {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)"
    )


if __name__ == "__main__":
    main()
