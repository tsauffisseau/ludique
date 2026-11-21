import numpy as np
import pandas as pd

from bgg_pipeline.clustering import elbow_k, name_segment, segment


def test_segment_names_are_business_readable():
    cuts = (80, 300)
    assert name_segment(25, 1.3, 120, cuts) == "Quick family games"
    assert name_segment(60, 2.2, 2000, cuts) == "Popular mid-length strategy games"
    assert name_segment(180, 3.4, 40, cuts) == "Niche long expert games"


def test_elbow_detects_the_knee():
    selection = pd.DataFrame({"k": range(2, 9), "inertia": [1000, 400, 150, 130, 115, 105, 98]})
    assert elbow_k(selection) == 4


def test_segmentation_recovers_three_planted_segments():
    rng = np.random.default_rng(0)
    blobs = [  # (playing_time, weight, users_rated) archetypes
        (20, 1.2, 100),
        (60, 2.3, 3000),
        (200, 3.8, 150),
    ]
    rows = []
    for i, (t, w, u) in enumerate(blobs):
        for _ in range(80):
            rows.append(
                {
                    "game_id": len(rows) + 1,
                    "game_name": f"g{len(rows)}",
                    "playing_time": t * rng.lognormal(0, 0.1),
                    "weight_complexity": w + rng.normal(0, 0.1),
                    "users_rated": u * rng.lognormal(0, 0.2),
                    "average_rating": 6 + i * 0.5,
                    "owned": 100,
                }
            )
    result = segment(pd.DataFrame(rows))
    assert result.chosen_k == 3
    assert result.profiles.n_games.tolist() == [80, 80, 80]
    # Segment ids are ordered by complexity: 1 = lightest
    assert result.profiles.avg_weight.is_monotonic_increasing
    light, popular, heavy = result.profiles.segment_name.tolist()
    assert "quick family games" in light.lower()
    assert popular == "Popular mid-length strategy games"
    assert "long expert games" in heavy.lower()
