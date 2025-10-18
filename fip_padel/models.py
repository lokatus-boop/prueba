"""Data models for FIP Padel scraping utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class MatchStats:
    """Statistics captured for a single match.

    The statistics are stored in a mapping keyed by the name of the metric. The
    values are plain strings so we can preserve whatever format the website
    provides (e.g. ``6-4 3-6 7-6`` for a score, ``62%`` for a percentage, etc.).
    """

    values: Dict[str, str] = field(default_factory=dict)

    def merge(self, other: "MatchStats") -> None:
        """Merge another :class:`MatchStats` into this instance.

        The website often duplicates statistics across different blocks. The
        ``merge`` method keeps the first value for each key to avoid losing any
        information that may already have been normalised.
        """

        for key, value in other.values.items():
            self.values.setdefault(key, value)

    def as_rows(self) -> List[str]:
        """Return a list of strings describing the statistics."""

        return [f"{key}: {value}" for key, value in self.values.items()]


@dataclass
class Match:
    """Information about an individual match inside a tournament."""

    tournament: str
    url: str
    round: Optional[str]
    day: Optional[str]
    category: Optional[str]
    start_time: Optional[datetime]
    team_one: List[str]
    team_two: List[str]
    score: Optional[str]
    stats: MatchStats = field(default_factory=MatchStats)


@dataclass
class Tournament:
    """Representation of a Premier Padel tournament."""

    name: str
    url: str
    location: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    matches: List[Match] = field(default_factory=list)


@dataclass
class RankingEntry:
    """Entry in either the official ranking or the race."""

    position: int
    player: str
    points: Optional[int]
    nation: Optional[str] = None
    partner: Optional[str] = None
    category: Optional[str] = None  # "male" or "female"
    ranking_type: Optional[str] = None  # "ranking" or "race"


PlayerMatches = List[Match]
PlayerStatsIndex = Dict[str, PlayerMatches]
