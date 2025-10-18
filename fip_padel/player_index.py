"""Utilities for aggregating player information."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set

from .models import Match, RankingEntry


@dataclass
class PlayerProfile:
    """Aggregated information for a single player."""

    name: str
    category: Optional[str] = None
    matches: List[Match] = field(default_factory=list)
    partners: Set[str] = field(default_factory=set)
    ranking: Optional[RankingEntry] = None
    race: Optional[RankingEntry] = None

    def summary(self) -> str:
        race_position = self.race.position if self.race else "-"
        ranking_position = self.ranking.position if self.ranking else "-"
        return (
            f"{self.name} — Race: {race_position} | Ranking: {ranking_position} | "
            f"Partidos: {len(self.matches)}"
        )


class PlayerIndex:
    """A dictionary like structure to track player information."""

    def __init__(self) -> None:
        self._profiles: Dict[str, PlayerProfile] = {}

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------
    def add_match(self, match: Match) -> None:
        for team in (match.team_one, match.team_two):
            for player in team:
                profile = self._get_or_create_profile(player)
                profile.matches.append(match)
                partners = set(team) - {player}
                profile.partners.update(partners)

    def add_ranking_entries(self, entries: Iterable[RankingEntry]) -> None:
        for entry in entries:
            profile = self._get_or_create_profile(entry.player)
            profile.category = profile.category or entry.category
            if entry.ranking_type == "ranking":
                if not profile.ranking or entry.position < (profile.ranking.position or 9999):
                    profile.ranking = entry
            elif entry.ranking_type == "race":
                if not profile.race or entry.position < (profile.race.position or 9999):
                    profile.race = entry

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def search(self, name: str) -> List[PlayerProfile]:
        name = name.lower().strip()
        matches = [profile for key, profile in self._profiles.items() if name in key]
        matches.sort(key=lambda profile: profile.name)
        return matches

    def get(self, name: str) -> Optional[PlayerProfile]:
        return self._profiles.get(name.lower())

    def all(self) -> List[PlayerProfile]:
        return sorted(self._profiles.values(), key=lambda profile: profile.name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_or_create_profile(self, name: str) -> PlayerProfile:
        key = name.lower().strip()
        profile = self._profiles.get(key)
        if not profile:
            profile = PlayerProfile(name=name.strip())
            self._profiles[key] = profile
        return profile
