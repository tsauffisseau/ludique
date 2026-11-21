from bgg_pipeline.parse import parse_payload


def by_id(records):
    return {r["game_id"]: r for r in records}


def test_expansions_are_ignored(snapshot_1):
    records, _ = parse_payload(snapshot_1)
    assert sorted(r["game_id"] for r in records) == [1, 2, 3, 5]


def test_clean_game_is_fully_parsed(snapshot_1):
    alpha = by_id(parse_payload(snapshot_1)[0])[1]
    assert alpha["game_name"] == "Alpha"  # primary name, not the alternate
    assert alpha["year_published"] == 2018
    assert (alpha["min_players"], alpha["max_players"]) == (2, 4)
    assert (alpha["best_with_min"], alpha["best_with_max"]) == (3, 4)
    assert alpha["average_rating"] == 7.5
    assert alpha["bgg_rank"] == 1500
    assert alpha["weight_complexity"] == 2.5
    assert alpha["description"] == 'A game about "alphas".\n\nSecond line.'


def test_bgg_zero_means_unknown(snapshot_1):
    """BGG encodes missing values as 0: they must become NULL, not drag averages down."""
    beta = by_id(parse_payload(snapshot_1)[0])[2]
    for field in (
        "year_published",
        "playing_time",
        "min_age",
        "average_rating",
        "bayes_average",
        "weight_complexity",
        "bgg_rank",
        "best_with_min",
    ):
        assert beta[field] is None, field
    assert beta["users_rated"] == 0  # a real zero count stays 0
    assert beta["description"] is None


def test_single_best_player_count(snapshot_1):
    gamma = by_id(parse_payload(snapshot_1)[0])[3]
    assert (gamma["best_with_min"], gamma["best_with_max"]) == (1, 1)


def test_links_are_typed(snapshot_1):
    _, links = parse_payload(snapshot_1)
    alpha_links = {(lk["link_type"], lk["link_name"]) for lk in links if lk["game_id"] == 1}
    assert ("mechanic", "Hand Management") in alpha_links
    assert ("category", "Card Game") in alpha_links
    assert ("designer", "Jane Doe") in alpha_links
    assert ("publisher", "Acme Games") in alpha_links
