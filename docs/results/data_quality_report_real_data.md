# Data Quality Report

_Generated 2026-11-22 21:28 UTC by `bgg_pipeline.data_quality`._

**22 passed · 9 warnings · 0 failures** (pipeline OK)

## Lineage (Bronze → Silver)

| Step | Rows |
|---|---:|
| Bronze Parquet files | 6 |
| Raw API responses (HTTP 200) | 969 |
| Game records parsed from XML | 8,728 |
| Duplicates removed (one snapshot per game per day) | 0 |
| Rejected by contract (quarantine) | 0 |
| Games in Silver | 4,364 |
| Dated metric snapshots in Silver (game × date) | 8,728 |
| Distinct snapshot dates | 2 |
| Game ↔ taxonomy links in Silver | 44,357 |

## Checks

| Status | Layer | Check | Description | Failing rows |
|---|---|---|---|---:|
| ⚠️ WARN | gold | `warn_extreme_playing_time` | playing time above 24 h (monster wargames or data entry errors - review before averaging) | 7 |
| ⚠️ WARN | gold | `warn_future_year` | games announced for a future year (not yet released, excluded from market marts) | 26 |
| ⚠️ WARN | gold | `warn_reliable_game_without_mechanic` | well-rated games (>= 30 ratings) with no mechanic assigned - invisible in mechanic marts | 53 |
| ⚠️ WARN | silver | `silver_min_gt_max_playtime` | min_playtime > max_playtime | 3 |
| ⚠️ WARN | silver | `silver_no_mechanic` | game without any mechanic link | 570 |
| ⚠️ WARN | silver | `silver_playtime_over_24h` | playing_time > 24 h | 7 |
| ⚠️ WARN | silver | `silver_rated_without_weight` | >= 30 ratings but no complexity vote | 23 |
| ⚠️ WARN | silver | `silver_year_before_1900` | year_published < 1900 (traditional/ancient games) | 38 |
| ⚠️ WARN | silver | `silver_year_in_future` | year_published > 2026 | 26 |
| ✅ PASS | gold | `accepted_range_metrics` | ratings in [1, 10], weight in [1, 5], counters non-negative | 0 |
| ✅ PASS | gold | `assert_tables_not_empty` | every star-schema table is populated | 0 |
| ✅ PASS | gold | `bridge_weights_sum_to_one` | allocation weights sum to 1 per game, so allocated measures never double count | 0 |
| ✅ PASS | gold | `games_have_a_snapshot` | every game of dim_game has at least one row in the snapshot fact | 0 |
| ✅ PASS | gold | `rating_requires_votes` | a snapshot with zero ratings must not carry an average rating | 0 |
| ✅ PASS | gold | `relationships_bridges` | every bridge row points to an existing game and dimension member | 0 |
| ✅ PASS | gold | `relationships_fact` | every fact row points to an existing game, snapshot date and year (referential integrity) | 0 |
| ✅ PASS | gold | `unique_bridge_pairs` | bridge tables contain no duplicated (game, member) pair | 0 |
| ✅ PASS | gold | `unique_dimension_keys` | dimension keys are unique (also enforced by PRIMARY KEY constraints) | 0 |
| ✅ PASS | gold | `unique_fact_grain` | fact_game_snapshot has exactly one row per game per snapshot date (declared grain) | 0 |
| ✅ PASS | gold | `warn_player_count_inconsistent` | min_players greater than max_players (source data entry error on BGG) | 0 |
| ✅ PASS | gold | `warn_rank_jump` | rank moved by more than 5 000 places between two consecutive snapshots (re-check the source) | 0 |
| ✅ PASS | silver | `silver_completeness_game_id` | game_id filled for >= 100% of games (actual 100.0%) | 0 |
| ✅ PASS | silver | `silver_completeness_game_name` | game_name filled for >= 100% of games (actual 100.0%) | 0 |
| ✅ PASS | silver | `silver_completeness_max_players` | max_players filled for >= 90% of games (actual 96.2%) | 0 |
| ✅ PASS | silver | `silver_completeness_min_players` | min_players filled for >= 90% of games (actual 98.5%) | 0 |
| ✅ PASS | silver | `silver_completeness_playing_time` | playing_time filled for >= 75% of games (actual 80.3%) | 0 |
| ✅ PASS | silver | `silver_completeness_users_rated` | users_rated filled for >= 100% of games (actual 100.0%) | 0 |
| ✅ PASS | silver | `silver_completeness_year_published` | year_published filled for >= 90% of games (actual 92.4%) | 0 |
| ✅ PASS | silver | `silver_min_gt_max_players` | min_players > max_players | 0 |
| ✅ PASS | silver | `silver_quarantine` | records rejected by the Pydantic contract (see rejected_records.parquet) | 0 |
| ✅ PASS | silver | `silver_unique_game_id` | game_id is unique | 0 |

## Completeness of Silver `games`

| Column | % non-null |
|---|---:|
| `bgg_rank` | 23.0 % |
| `bayes_average` | 23.5 % |
| `best_with_min` | 34.4 % |
| `best_with_max` | 34.4 % |
| `weight_complexity` | 44.8 % |
| `average_rating` | 77.7 % |
| `rating_stddev` | 77.7 % |
| `playing_time` | 80.3 % |
| `max_playtime` | 80.3 % |
| `min_playtime` | 81.5 % |
| `min_age` | 81.9 % |
| `year_published` | 92.4 % |
| `thumbnail_url` | 93.3 % |
| `image_url` | 93.3 % |
| `max_players` | 96.2 % |
| `min_players` | 98.5 % |
| `game_id` | 100.0 % |
| `game_name` | 100.0 % |
| `users_rated` | 100.0 % |
| `num_weights` | 100.0 % |
| `owned` | 100.0 % |
| `trading` | 100.0 % |
| `wanting` | 100.0 % |
| `wishing` | 100.0 % |
| `num_comments` | 100.0 % |
| `description` | 100.0 % |
| `source_run_id` | 100.0 % |
| `source_fetched_at` | 100.0 % |

## Examples of flagged rows

**`silver_min_gt_max_playtime`** — min_playtime > max_playtime

```json
{"game_id": 126026, "game_name": "Gato Leader", "year_published": 2016, "playing_time": 60}
{"game_id": 369763, "game_name": "Clash of Decks: Elusive", "year_published": 2022, "playing_time": 8}
{"game_id": 463680, "game_name": "Drinking Quest: Sky Rum", "year_published": 2026, "playing_time": 1}
```

**`silver_playtime_over_24h`** — playing_time > 24 h

```json
{"game_id": 4102, "game_name": "Europa Universalis", "year_published": 1993, "playing_time": 3600}
{"game_id": 9112, "game_name": "Omaha: The Bloody Beach", "year_published": 1991, "playing_time": 3600}
{"game_id": 88190, "game_name": "Hurtgen: Hell's Forest", "year_published": 2012, "playing_time": 2400}
{"game_id": 202435, "game_name": "To Take Washington: Jubal Early's Summer 1864 Campaign", "year_published": 2019, "playing_time": 3600}
{"game_id": 314577, "game_name": "Pacific War: The Struggle Against Japan, 1941-1945 (Second Edition)", "year_published": 2022, "playing_time": 6000}
```

**`silver_year_in_future`** — year_published > 2026

```json
{"game_id": 338455, "game_name": "Werewolf: The Apocalypse – Retaliation", "year_published": 2027, "playing_time": 60}
{"game_id": 357204, "game_name": "Rainbow Blvd.", "year_published": 2027, "playing_time": 75}
{"game_id": 434875, "game_name": "Intricatus", "year_published": 2027, "playing_time": 15}
{"game_id": 456054, "game_name": "Tiny Homes", "year_published": 2027, "playing_time": 45}
{"game_id": 459332, "game_name": "War of the Words", "year_published": 2027, "playing_time": 60}
```

**`silver_year_before_1900`** — year_published < 1900 (traditional/ancient games)

```json
{"game_id": 2397, "game_name": "Backgammon", "year_published": 1635, "playing_time": 30}
{"game_id": 5546, "game_name": "Marbles", "year_published": -3000, "playing_time": 10}
{"game_id": 5878, "game_name": "Lotería", "year_published": 1887, "playing_time": 10}
{"game_id": 6471, "game_name": "Panguingue", "year_published": 1860, "playing_time": 60}
{"game_id": 10400, "game_name": "Patience", "year_published": 1783, "playing_time": 10}
```

**`silver_rated_without_weight`** — >= 30 ratings but no complexity vote

```json
{"game_id": 63898, "game_name": "UFO Attack", "year_published": 2010, "playing_time": 15}
{"game_id": 155201, "game_name": "Breitseite", "year_published": 2014, "playing_time": 10}
{"game_id": 176562, "game_name": "The Bremens", "year_published": 2015, "playing_time": 30}
{"game_id": 205478, "game_name": "Covenant", "year_published": 2016, "playing_time": 45}
{"game_id": 264672, "game_name": "ジャンキー (Junkie)", "year_published": 2018, "playing_time": 20}
```

**`silver_no_mechanic`** — game without any mechanic link

```json
{"game_id": 151, "game_name": "Piratenbillard", "year_published": 1989, "playing_time": 15}
{"game_id": 285, "game_name": "Monsters Ravage America", "year_published": 1998, "playing_time": 90}
{"game_id": 821, "game_name": "La Trel", "year_published": 1994, "playing_time": 60}
{"game_id": 1939, "game_name": "Kismet", "year_published": 1997, "playing_time": 15}
{"game_id": 2164, "game_name": "Square Off", "year_published": 1972, "playing_time": 10}
```

**`warn_extreme_playing_time`** — playing time above 24 h (monster wargames or data entry errors - review before averaging)

```json
{"game_id": 314577, "game_name": "Pacific War: The Struggle Against Japan, 1941-1945 (Second Edition)", "playing_time": 6000}
{"game_id": 9112, "game_name": "Omaha: The Bloody Beach", "playing_time": 3600}
{"game_id": 202435, "game_name": "To Take Washington: Jubal Early's Summer 1864 Campaign", "playing_time": 3600}
{"game_id": 4102, "game_name": "Europa Universalis", "playing_time": 3600}
{"game_id": 88190, "game_name": "Hurtgen: Hell's Forest", "playing_time": 2400}
```

**`warn_future_year`** — games announced for a future year (not yet released, excluded from market marts)

```json
{"game_id": 477516, "game_name": "Dice Valley", "year_published": 2027}
{"game_id": 459332, "game_name": "War of the Words", "year_published": 2027}
{"game_id": 478352, "game_name": "Flounder", "year_published": 2027}
{"game_id": 357204, "game_name": "Rainbow Blvd.", "year_published": 2027}
{"game_id": 461542, "game_name": "Godmaker", "year_published": 2028}
```

**`warn_reliable_game_without_mechanic`** — well-rated games (>= 30 ratings) with no mechanic assigned - invisible in mechanic marts

```json
{"game_id": 14758, "game_name": "Slammer"}
{"game_id": 125083, "game_name": "Things They Don't Teach You in School"}
{"game_id": 136609, "game_name": "Jenga BOOM"}
{"game_id": 7862, "game_name": "Birds, Bugs and Beans"}
{"game_id": 121195, "game_name": "Grandpa  Beck's Golf"}
```

