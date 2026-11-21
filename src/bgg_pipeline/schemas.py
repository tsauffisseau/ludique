"""Silver data contracts (Pydantic).

These are *hard* constraints: a record violating them is physically impossible or
unusable and is sent to quarantine (``rejected_records.parquet``) with the reason.

*Soft* anomalies (min_players > max_players, 60 000-minute wargames, games announced
for next year...) are legitimate BGG data: they are kept and surfaced by
``data_quality.py`` instead of being silently "fixed".
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

LINK_TYPES = {
    "boardgamemechanic": "mechanic",
    "boardgamecategory": "category",
    "boardgamedesigner": "designer",
    "boardgamepublisher": "publisher",
    "boardgamefamily": "family",
    "boardgameartist": "artist",
}


class GameLink(BaseModel):
    model_config = ConfigDict(frozen=True)

    game_id: int = Field(gt=0)
    link_type: str
    link_id: int = Field(gt=0)
    link_name: str = Field(min_length=1)

    @field_validator("link_type")
    @classmethod
    def known_type(cls, v: str) -> str:
        if v not in LINK_TYPES.values():
            raise ValueError(f"unknown link type {v!r}")
        return v


class GameRecord(BaseModel):
    """One board game as published by BGG, cleaned and typed."""

    model_config = ConfigDict(str_strip_whitespace=True)

    game_id: int = Field(gt=0)
    game_name: str = Field(min_length=1)
    year_published: int | None = Field(default=None, ge=-5000, le=2100)

    min_players: int | None = Field(default=None, ge=1, le=999)
    max_players: int | None = Field(default=None, ge=1, le=9999)
    best_with_min: int | None = Field(default=None, ge=1)
    best_with_max: int | None = Field(default=None, ge=1)
    playing_time: int | None = Field(default=None, ge=1)
    min_playtime: int | None = Field(default=None, ge=1)
    max_playtime: int | None = Field(default=None, ge=1)
    min_age: int | None = Field(default=None, ge=1, le=99)

    users_rated: int = Field(ge=0)
    average_rating: float | None = Field(default=None, ge=1, le=10)
    bayes_average: float | None = Field(default=None, ge=1, le=10)
    rating_stddev: float | None = Field(default=None, ge=0)
    bgg_rank: int | None = Field(default=None, ge=1)
    num_weights: int = Field(ge=0)
    weight_complexity: float | None = Field(default=None, ge=1, le=5)

    owned: int = Field(ge=0)
    trading: int = Field(ge=0)
    wanting: int = Field(ge=0)
    wishing: int = Field(ge=0)
    num_comments: int = Field(ge=0)

    description: str | None = None
    thumbnail_url: str | None = None
    image_url: str | None = None

    source_run_id: str
    source_fetched_at: datetime
