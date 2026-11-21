"""Game segmentation: K-means on duration, complexity and popularity.

Population: released games with >= 30 ratings (reliable) and a complexity vote.
Features (standardised):

* ``log_playing_time``  - duration, log-scaled (20 min vs 40 min matters more than 4 h vs 4h20)
* ``weight_complexity`` - BGG complexity, 1-5
* ``log_users_rated``   - popularity, log-scaled (ratings follow a power law)

Choosing k: silhouette score for k = 2..8, cross-checked with the elbow of the inertia
curve. k = 2 is excluded from the choice: it only separates "light" from "heavy", which
is not actionable for a publisher. Each segment is then named in business language from
its centroid (e.g. "Quick family games", "Popular mid-length strategy games").

Outputs (schema ``marts``): ``cluster_selection`` (k, inertia, silhouette),
``cluster_profiles`` (one row per segment) and ``game_clusters`` (game -> segment).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
import psycopg
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .load import query_df

logger = logging.getLogger(__name__)

FEATURES = ["log_playing_time", "weight_complexity", "log_users_rated"]
K_RANGE = range(2, 9)
MIN_K = 3
SEED = 42

POPULATION_SQL = """
SELECT g.game_id, g.game_name, g.playing_time, f.weight_complexity, f.users_rated,
       f.average_rating, f.owned
FROM fact_game_latest AS f
JOIN dim_game AS g ON g.game_id = f.game_id
WHERE g.is_rating_reliable AND g.is_released
  AND f.weight_complexity IS NOT NULL
  AND g.playing_time BETWEEN 5 AND 1440
"""


@dataclass
class SegmentationResult:
    selection: pd.DataFrame
    profiles: pd.DataFrame
    assignments: pd.DataFrame
    chosen_k: int
    elbow_k: int


def build_features(games: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "log_playing_time": np.log(games["playing_time"].astype(float)),
            "weight_complexity": games["weight_complexity"].astype(float),
            "log_users_rated": np.log(games["users_rated"].astype(float)),
        },
        index=games.index,
    )


def elbow_k(selection: pd.DataFrame) -> int:
    """Knee of the inertia curve: point farthest from the line joining both ends."""
    k = selection["k"].to_numpy(float)
    inertia = selection["inertia"].to_numpy(float)
    x = (k - k.min()) / (k.max() - k.min())
    y = (inertia - inertia.min()) / (inertia.max() - inertia.min())
    distance = np.abs(x + y - 1) / np.sqrt(2)  # distance to the line from (0, 1) to (1, 0)
    return int(k[int(np.argmax(distance))])


def select_k(x: np.ndarray, k_range=K_RANGE, seed: int = SEED) -> pd.DataFrame:
    rows = []
    for k in k_range:
        model = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(x)
        rows.append({"k": k, "inertia": model.inertia_, "silhouette": silhouette_score(x, model.labels_)})
    return pd.DataFrame(rows)


def name_segment(playing_time: float, weight: float, users_rated: float, popularity_cuts) -> str:
    """Business label from a centroid expressed in original units."""
    duration = "Quick" if playing_time <= 45 else "Mid-length" if playing_time <= 100 else "Long"
    audience = "family games" if weight < 1.9 else "strategy games" if weight < 2.8 else "expert games"
    low, high = popularity_cuts
    if users_rated < low:
        return f"Niche {duration.lower()} {audience}"
    if users_rated > high:
        return f"Popular {duration.lower()} {audience}"
    return f"{duration} {audience}"


def segment(games: pd.DataFrame, seed: int = SEED) -> SegmentationResult:
    features = build_features(games)
    scaler = StandardScaler().fit(features)
    x = scaler.transform(features)

    selection = select_k(x, seed=seed)
    candidates = selection[selection.k >= MIN_K]
    chosen_k = int(candidates.loc[candidates.silhouette.idxmax(), "k"])
    knee = elbow_k(selection)
    selection["is_chosen"] = selection.k == chosen_k

    model = KMeans(n_clusters=chosen_k, n_init=10, random_state=seed).fit(x)
    centroids = pd.DataFrame(scaler.inverse_transform(model.cluster_centers_), columns=FEATURES)

    # Popularity tiers relative to the population (terciles of log ratings).
    cuts = np.exp(np.quantile(features["log_users_rated"], [1 / 3, 2 / 3]))
    names = {
        i: name_segment(np.exp(c.log_playing_time), c.weight_complexity, np.exp(c.log_users_rated), cuts)
        for i, c in centroids.iterrows()
    }
    # Guarantee unique labels (two segments could share a description).
    seen: dict[str, int] = {}
    for i, name in sorted(names.items()):
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            names[i] = f"{name} ({seen[name]})"

    # Order segments by complexity so ids are stable and readable (1 = lightest).
    order = centroids.weight_complexity.sort_values().index
    remap = {old: new for new, old in enumerate(order, start=1)}

    assignments = games[["game_id"]].copy()
    assignments["segment_id"] = [remap[label] for label in model.labels_]
    assignments["segment_name"] = [names[label] for label in model.labels_]

    joined = games.join(assignments[["segment_id", "segment_name"]])
    profiles = (
        joined.groupby(["segment_id", "segment_name"])
        .agg(
            n_games=("game_id", "size"),
            median_playing_time=("playing_time", "median"),
            avg_weight=("weight_complexity", "mean"),
            median_users_rated=("users_rated", "median"),
            avg_rating=("average_rating", "mean"),
            median_owned=("owned", "median"),
        )
        .reset_index()
    )
    profiles["pct_of_games"] = (100 * profiles.n_games / profiles.n_games.sum()).round(1)
    profiles = profiles.round({"avg_weight": 2, "avg_rating": 2})
    return SegmentationResult(selection, profiles, assignments, chosen_k, knee)


def _write_table(con: psycopg.Connection, name: str, df: pd.DataFrame, ddl: str) -> None:
    con.execute(f"DROP TABLE IF EXISTS marts.{name} CASCADE")
    con.execute(f"CREATE TABLE marts.{name} ({ddl})")
    with con.cursor() as cur, cur.copy(f"COPY marts.{name} ({', '.join(df.columns)}) FROM STDIN") as copy:
        for row in df.itertuples(index=False, name=None):
            copy.write_row([v.item() if hasattr(v, "item") else v for v in row])


def run_segmentation(dsn: str, seed: int = SEED) -> SegmentationResult:
    games = query_df(dsn, POPULATION_SQL).reset_index(drop=True)
    if len(games) < 50:
        raise ValueError(f"Only {len(games)} reliable games: not enough to segment")
    result = segment(games, seed)

    with psycopg.connect(dsn) as con:
        _write_table(
            con,
            "cluster_selection",
            result.selection,
            "k INTEGER PRIMARY KEY, inertia DOUBLE PRECISION, silhouette DOUBLE PRECISION, is_chosen BOOLEAN",
        )
        _write_table(
            con,
            "cluster_profiles",
            result.profiles,
            "segment_id INTEGER PRIMARY KEY, segment_name TEXT, n_games INTEGER, "
            "median_playing_time DOUBLE PRECISION, avg_weight DOUBLE PRECISION, "
            "median_users_rated DOUBLE PRECISION, avg_rating DOUBLE PRECISION, "
            "median_owned DOUBLE PRECISION, pct_of_games DOUBLE PRECISION",
        )
        _write_table(
            con,
            "game_clusters",
            result.assignments,
            "game_id INTEGER PRIMARY KEY REFERENCES dw.dim_game (game_id), "
            "segment_id INTEGER REFERENCES marts.cluster_profiles (segment_id), segment_name TEXT",
        )
        con.commit()

    best = result.selection.set_index("k").loc[result.chosen_k, "silhouette"]
    logger.info(
        "Segmentation: k=%d (silhouette %.3f; elbow suggests k=%d) on %d games: %s",
        result.chosen_k,
        best,
        result.elbow_k,
        len(games),
        ", ".join(result.profiles.segment_name),
    )
    return result
