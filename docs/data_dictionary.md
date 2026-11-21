# Data dictionary: Gold layer (PostgreSQL)

Database: PostgreSQL 16. Schemas: `silver` → `staging` → `intermediate` → `dw` (star schema) → `marts`.
`python -m bgg_pipeline export` also writes every `dw` table to `data/gold/<table>/<table>.parquet`.

Conventions
- `*_id` columns are BoardGameGeek natural keys (stable, unique per entity on BGG).
- `NULL` means *unknown at source*. BGG encodes unknown as `0`; those zeros are converted to `NULL` in Silver.
- **Reliable** = `users_rated >= 30`, the threshold BGG itself uses to rank a game. Quality metrics (ratings, complexity) use reliable games only.
- Constraints are declared in the database (PK, FK, CHECK) **and** re-tested by `sql/tests/`.

## Star schema (`dw`)

| Table | Type | Grain | Primary key | Load strategy |
|---|---|---|---|---|
| `fact_game_snapshot` | Fact (periodic snapshot) | one row per game per snapshot date | `(game_id, snapshot_date_key)` | incremental, high-watermark + idempotent upsert |
| `fact_game_latest` | View | latest snapshot of each game | `game_id` | – |
| `dim_game` | Dimension | one row per game | `game_id` | upsert (SCD 1) |
| `dim_date` | Dimension (snapshot date) | one row per day | `date_key` (YYYYMMDD) | append |
| `dim_year` | Dimension (publication year) | one row per year, `0` = Unknown | `year_published` | append |
| `dim_mechanic` | Dimension | one row per mechanic | `mechanic_id` | upsert (SCD 1) |
| `dim_category` | Dimension | one row per category / theme | `category_id` | upsert (SCD 1) |
| `dim_designer` | Dimension | one row per designer | `designer_id` | upsert (SCD 1) |
| `dim_publisher` | Dimension | one row per publisher | `publisher_id` | upsert (SCD 1) |
| `bridge_game_mechanic` / `_category` / `_designer` / `_publisher` | Bridge (N-N) | one row per (game, member) | `(game_id, member_id)` | replaced for the games of the load |

### `fact_game_snapshot`

| Column | Type | Additivity | Description |
|---|---|---|---|
| `game_id` | INTEGER | key | FK → `dim_game` |
| `snapshot_date_key` | INTEGER | key | FK → `dim_date` (YYYYMMDD) |
| `year_published` | INTEGER | key | FK → `dim_year` (`0` = unknown member) |
| `average_rating` | DOUBLE | non-additive | Mean user rating, 1–10. NULL if no rating |
| `bayes_average` | DOUBLE | non-additive | BGG "Geek rating" (shrunk toward the mean); NULL if not ranked |
| `rating_stddev` | DOUBLE | non-additive | Standard deviation of ratings (polarisation) |
| `users_rated` | INTEGER | semi-additive | Number of ratings (additive across games, not across dates) |
| `bgg_rank` | INTEGER | non-additive | Overall board game rank (NULL = not ranked) |
| `weight_complexity` | DOUBLE | non-additive | Average complexity vote, 1 (light) – 5 (heavy) |
| `num_weights` | INTEGER | semi-additive | Number of complexity votes |
| `owned` | INTEGER | semi-additive | Copies in user collections: **market-penetration proxy** (BGG has no sales data) |
| `wishing` | INTEGER | semi-additive | Wishlists: **unmet-demand proxy** |
| `wanting`, `trading` | INTEGER | semi-additive | Want-in-trade / for-trade lists |
| `num_comments` | INTEGER | semi-additive | Comment count (engagement) |
| `loaded_at` | TIMESTAMPTZ | – | When the row was inserted or last changed (audit) |

### `dim_game`

| Column | Description |
|---|---|
| `game_id`, `game_name`, `bgg_url` | BGG id, primary name, link |
| `min_players`, `max_players`, `best_with_min`, `best_with_max` | Publisher and community-voted player counts |
| `playing_time`, `min_playtime`, `max_playtime`, `min_age` | Minutes / years |
| `weight_bucket` | Light / Medium-light / Medium / Medium-heavy / Heavy (prefixed `1.`–`5.` for sorting, `0. Unknown`) |
| `playtime_bucket` | Filler ≤ 30 min … Epic > 4 h |
| `player_count_profile` | Solo only / Up to 2 / Up to 4 / Up to 6 / 7+ |
| `supports_solo` | `min_players = 1` |
| `is_rating_reliable` | `users_rated >= 30` (latest snapshot) |
| `is_released` | FALSE for games announced for a future year (excluded from market marts) |
| `n_mechanics`, `n_categories`, `n_designers`, `n_publishers` | Bridge cardinalities |
| `description`, `thumbnail_url`, `updated_at` | Display attributes, last upsert |

### `dim_date` · `dim_year`

| Column | Description |
|---|---|
| `date_key`, `date_actual`, `year`, `quarter`, `month`, `month_name`, `iso_week`, `day_of_week`, `day_name`, `is_weekend` | Calendar of snapshot dates |
| `year_published` | Year (negative for ancient games); `0` = Unknown member |
| `decade`, `decade_label` | `1990`, `"1990s"`; everything before 1950 grouped as `"Before 1950"` |
| `market_era` | Classic (< 1980) · Hobby emergence (1980–94) · Eurogame era (1995–2009) · Crowdfunding boom (2010–19) · Post-2020 |

### Taxonomy dimensions and bridges

Each `dim_<member>` has `<member>_id`, `<member>_name`, `n_games` and `is_placeholder`
(BGG pseudo-entries such as "(Uncredited)" or "(Self-Published)").

`allocation_weight = 1 / number of members of that type for the game`. Multiply an
additive measure by it to split the measure across members without double counting (a
game with 4 mechanics gives ¼ of its owned copies to each). The `bridge_weights_sum_to_one`
test checks that the weights add up to 1 for every game.

## Marts (`marts`)

| Object | Business question | Grain |
|---|---|---|
| `mart_catalog_kpis` | Headline KPIs (incl. number of snapshots) | 1 row |
| `mart_decade_trends` | Q1: supply, complexity and ratings per decade | decade |
| `mart_top_mechanics_trends` | Q2: rating lift, market share and momentum of each mechanic | mechanic |
| `mart_complexity_vs_rating` | Q3: rating & reach by complexity bucket, per era (GROUPING SETS) | era × weight bucket |
| `mart_niche_opportunities` | Q4: mechanic × category niches scored on quality, unmet demand and supply | mechanic × category |
| `mart_rank_movers` | History: rank and rating change between the two latest snapshots | game |
| `cluster_selection` | K-means model selection: inertia and silhouette per k | k |
| `cluster_profiles` | One row per segment: size, median duration, complexity, popularity, rating | segment |
| `game_clusters` | Segment of each clustered game | game |

Metric definitions:

- **rating_lift** = mechanic's average rating − catalogue average (reliable games).
- **owned_share_pct** = Σ(owned × allocation_weight) for the mechanic / Σ owned. Sums to 100 % across mechanics.
- **momentum_index** = (share of 2015+ releases using the mechanic) / (same share for 2000–2014 releases). Above 1, publishers adopt the mechanic more and more. It is NULL when the mechanic has fewer than 5 games in 2000–2014 (base too small).
- **wish_to_own_ratio** = Σ wishing / Σ owned in the niche.
- **opportunity_score** = z(avg rating) + z(ln(1 + wish_to_own_ratio)) − z(ln n_games). Z-scores are computed across niches with at least 3 reliable games and clipped to [−3, 3]; unreleased games are excluded.
- **rank_change** = previous rank − latest rank (positive = the game climbed).
