"""HTTP client and scraping helpers for padelfip.com."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import requests
from bs4 import BeautifulSoup

from .models import Match, MatchStats, RankingEntry, Tournament

logger = logging.getLogger(__name__)

DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d",
)


@dataclass
class _RankingConfig:
    url: str
    category: str
    ranking_type: str


class FIPPadelClient:
    """Scrape information from padelfip.com.

    The client is intentionally defensive: the website changes its markup
    frequently and frequently embeds data inside ``script`` tags. Whenever a
    piece of information cannot be parsed the corresponding field is left as
    ``None`` so downstream consumers can decide how to handle the missing data.
    """

    PREMIER_PADEL_CALENDAR = (
        "https://www.padelfip.com/es/calendario-premier-padel/?events-year={year}"
    )

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0 Safari/537.36"
            ),
        )

    # ------------------------------------------------------------------
    # Network helpers
    # ------------------------------------------------------------------
    def _get_soup(self, url: str) -> BeautifulSoup:
        logger.debug("Fetching %s", url)
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_premier_padel_tournaments(self, year: int = 2025) -> List[Tournament]:
        """Return a list of Premier Padel tournaments for ``year``."""

        url = self.PREMIER_PADEL_CALENDAR.format(year=year)
        soup = self._get_soup(url)

        tournaments: List[Tournament] = []
        for article in soup.select("article"):
            tournament = self._parse_tournament_card(article)
            if not tournament:
                continue
            tournament.matches = self._load_tournament_matches(tournament)
            tournaments.append(tournament)
        return tournaments

    def get_rankings(self) -> Dict[str, List[RankingEntry]]:
        """Fetch both the ranking and the race for men and women."""

        configs = [
            _RankingConfig(
                url="https://www.padelfip.com/es/ranking-masculino/",
                category="male",
                ranking_type="ranking",
            ),
            _RankingConfig(
                url="https://www.padelfip.com/es/ranking-femenino/",
                category="female",
                ranking_type="ranking",
            ),
            _RankingConfig(
                url="https://www.padelfip.com/es/race-fip-top-100-masculino/",
                category="male",
                ranking_type="race",
            ),
            _RankingConfig(
                url="https://www.padelfip.com/es/race-fip-top-100-femenino/",
                category="female",
                ranking_type="race",
            ),
        ]

        results: Dict[str, List[RankingEntry]] = {"ranking": [], "race": []}
        for config in configs:
            entries = self._parse_ranking_page(config)
            results.setdefault(config.ranking_type, []).extend(entries)
        return results

    # ------------------------------------------------------------------
    # Tournament parsing
    # ------------------------------------------------------------------
    def _parse_tournament_card(self, article: BeautifulSoup) -> Optional[Tournament]:
        classes = article.get("class", [])
        if not any("tribe" in cls for cls in classes):
            # Ignore unrelated article blocks
            return None

        link = article.find("a", href=True)
        if not link:
            return None
        name = _clean_text(link.get_text())
        url = link["href"].strip()

        location_el = article.find(class_=re.compile("event-venue"))
        location = _clean_text(location_el.get_text()) if location_el else None

        start_date = None
        end_date = None
        time_elements = article.select("time")
        if time_elements:
            parsed_dates = [self._parse_datetime(time_el.get("datetime")) for time_el in time_elements]
            parsed_dates = [dt for dt in parsed_dates if dt]
            if parsed_dates:
                start_date = parsed_dates[0]
                if len(parsed_dates) > 1:
                    end_date = parsed_dates[-1]

        return Tournament(
            name=name,
            url=url,
            location=location,
            start_date=start_date,
            end_date=end_date,
        )

    def _load_tournament_matches(self, tournament: Tournament) -> List[Match]:
        try:
            soup = self._get_soup(tournament.url)
        except requests.HTTPError as exc:  # pragma: no cover - defensive
            logger.warning("Unable to fetch %s: %s", tournament.url, exc)
            return []

        matches = []
        matches.extend(self._extract_matches_from_jsonld(soup, tournament))
        matches.extend(self._extract_matches_from_tables(soup, tournament))
        merged = self._merge_duplicate_matches(matches)
        logger.debug("Found %d matches for %s", len(merged), tournament.name)
        return merged

    def _extract_matches_from_jsonld(self, soup: BeautifulSoup, tournament: Tournament) -> List[Match]:
        matches: List[Match] = []
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue
            for item in _ensure_list(data):
                matches.extend(self._parse_jsonld_event(item, tournament))
        return matches

    def _parse_jsonld_event(self, data: dict, tournament: Tournament) -> List[Match]:
        result: List[Match] = []
        if not isinstance(data, dict):
            return result

        data_type = data.get("@type")
        if data_type not in {"Event", "SportsEvent", "Game"}:
            return result

        sub_events = data.get("subEvent")
        if sub_events:
            for sub in _ensure_list(sub_events):
                result.extend(self._parse_jsonld_event(sub, tournament))
            return result

        name = _clean_text(data.get("name"))
        round_name = _clean_text(data.get("eventType") or data.get("eventStatus"))
        start_time = self._parse_datetime(data.get("startDate"))
        description = data.get("description")
        day = None
        if description:
            day_match = re.search(r"D[ií]a\s+(\d+)", description, re.IGNORECASE)
            if day_match:
                day = day_match.group(0)

        competitors = data.get("competitor") or data.get("performer")
        team_one: List[str] = []
        team_two: List[str] = []
        if competitors:
            teams = _ensure_list(competitors)
            if len(teams) == 2:
                team_one = _extract_names_from_competitor(teams[0])
                team_two = _extract_names_from_competitor(teams[1])
            else:
                names = []
                for team in teams:
                    names.extend(_extract_names_from_competitor(team))
                # Attempt to split into teams of two players
                team_one = names[:2]
                team_two = names[2:4] if len(names) > 2 else []

        score = None
        stats = MatchStats()
        if description:
            score_match = re.search(r"(\d+-\d+(?:\s+\(\d+-\d+\))?(?:\s+\d+-\d+)*)", description)
            if score_match:
                score = score_match.group(1)
        if data.get("aggregateRating"):
            stats.values["Aggregate rating"] = str(data["aggregateRating"])
        if data.get("result"):
            stats.values["Resultado"] = _clean_text(data["result"])

        if not team_one and not team_two and not score:
            # The event may not be a match at all
            return result

        result.append(
            Match(
                tournament=tournament.name,
                url=tournament.url,
                round=round_name or name,
                day=day,
                category=None,
                start_time=start_time,
                team_one=team_one,
                team_two=team_two,
                score=score,
                stats=stats,
            )
        )
        return result

    def _extract_matches_from_tables(self, soup: BeautifulSoup, tournament: Tournament) -> List[Match]:
        matches: List[Match] = []
        for table in soup.select("table"):
            headers = [
                _clean_text(th.get_text())
                for th in table.select("thead th") or table.select("tr th")
            ]
            header_text = " ".join(headers).lower()
            if not headers or not any(
                keyword in header_text for keyword in ["partido", "match", "pareja", "resultado", "score"]
            ):
                continue

            for row in table.select("tbody tr") or table.select("tr"):
                cells = [_clean_text(cell.get_text(" ")) for cell in row.find_all("td")]
                if len(cells) < 3:
                    continue
                # Heuristic: [round/day], [team1 vs team2], [score]
                round_name = cells[0]
                players_text = cells[1]
                score = cells[2]

                teams = re.split(r"vs|VS|v\.|-", players_text)
                team_one = _split_players(teams[0]) if teams else _split_players(players_text)
                team_two = _split_players(teams[1]) if len(teams) > 1 else []

                matches.append(
                    Match(
                        tournament=tournament.name,
                        url=tournament.url,
                        round=round_name or None,
                        day=None,
                        category=None,
                        start_time=None,
                        team_one=team_one,
                        team_two=team_two,
                        score=score if score else None,
                        stats=MatchStats(),
                    )
                )
        return matches

    def _merge_duplicate_matches(self, matches: Iterable[Match]) -> List[Match]:
        index: Dict[str, Match] = {}
        for match in matches:
            key_parts = [
                match.round or "",
                "-".join(match.team_one),
                "-".join(match.team_two),
                match.score or "",
            ]
            key = "|".join(key_parts)
            existing = index.get(key)
            if existing:
                existing.stats.merge(match.stats)
                existing.day = existing.day or match.day
                existing.category = existing.category or match.category
                existing.start_time = existing.start_time or match.start_time
            else:
                index[key] = match
        return list(index.values())

    # ------------------------------------------------------------------
    # Ranking parsing
    # ------------------------------------------------------------------
    def _parse_ranking_page(self, config: _RankingConfig) -> List[RankingEntry]:
        try:
            soup = self._get_soup(config.url)
        except requests.HTTPError as exc:  # pragma: no cover - defensive
            logger.warning("Unable to fetch ranking %s: %s", config.url, exc)
            return []

        entries: List[RankingEntry] = []
        for table in soup.select("table"):
            headers = [
                _clean_text(th.get_text())
                for th in table.select("thead th") or table.select("tr th")
            ]
            header_text = " ".join(headers).lower()
            if not headers or not any(keyword in header_text for keyword in ["jugador", "player", "puntos", "points"]):
                continue

            for row in table.select("tbody tr") or table.select("tr"):
                cells = [_clean_text(cell.get_text(" ")) for cell in row.find_all("td")]
                if len(cells) < 2:
                    continue
                try:
                    position = int(re.sub(r"[^0-9]", "", cells[0]) or 0)
                except ValueError:
                    position = 0
                player = cells[1]
                points = _parse_int(cells[2]) if len(cells) > 2 else None
                nation = cells[3] if len(cells) > 3 else None
                partner = cells[4] if len(cells) > 4 else None

                entries.append(
                    RankingEntry(
                        position=position,
                        player=player,
                        points=points,
                        nation=nation,
                        partner=partner,
                        category=config.category,
                        ranking_type=config.ranking_type,
                    )
                )
        return entries

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------
    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _ensure_list(value: object) -> List[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _extract_names_from_competitor(data: object) -> List[str]:
    if data is None:
        return []
    if isinstance(data, str):
        return _split_players(data)
    if isinstance(data, dict):
        name = data.get("name") or data.get("alternateName")
        if name:
            return _split_players(name)
        if "competitor" in data:
            return _extract_names_from_competitor(data["competitor"])
    return []


def _split_players(raw: str) -> List[str]:
    cleaned = _clean_text(raw)
    if not cleaned:
        return []
    separators = ["/", "-", "&", " y ", " and "]
    for sep in separators:
        if sep in cleaned:
            return [part.strip() for part in re.split(re.escape(sep), cleaned) if part.strip()]
    return [cleaned]


def _parse_int(raw: str) -> Optional[int]:
    digits = re.sub(r"[^0-9]", "", raw or "")
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None
