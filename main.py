"""CLI para recopilar información de torneos Premier Padel 2025."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from typing import Iterable

from fip_padel.client import FIPPadelClient
from fip_padel.models import Match, Tournament
from fip_padel.player_index import PlayerIndex, PlayerProfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_player_index(tournaments: Iterable[Tournament], rankings: dict) -> PlayerIndex:
    index = PlayerIndex()
    for entries in rankings.values():
        index.add_ranking_entries(entries)
    for tournament in tournaments:
        for match in tournament.matches:
            index.add_match(match)
    return index


def format_match_line(player: str, match: Match) -> str:
    start = match.start_time.strftime("%d-%m-%Y %H:%M") if match.start_time else "Fecha desconocida"
    round_name = match.round or "Ronda"
    if player in match.team_one:
        partners = ", ".join([p for p in match.team_one if p != player]) or "Sin compañero"
        opponents = ", ".join(match.team_two) or "Sin rival"
    else:
        partners = ", ".join([p for p in match.team_two if p != player]) or "Sin compañero"
        opponents = ", ".join(match.team_one) or "Sin rival"
    score = match.score or "Sin marcador"
    stats = "; ".join(match.stats.as_rows()) or "Sin estadísticas registradas"
    return (
        f"[{start}] {match.tournament} — {round_name}\n"
        f"    Pareja: {partners}\n"
        f"    Rivales: {opponents}\n"
        f"    Marcador: {score}\n"
        f"    Estadísticas: {stats}"
    )


def show_player_detail(profile: PlayerProfile) -> None:
    print("=" * 80)
    print(profile.summary())
    if profile.ranking:
        print(
            f"Ranking {profile.ranking.category or '-'} #{profile.ranking.position} "
            f"con {profile.ranking.points or '-'} puntos"
        )
    if profile.race:
        print(
            f"Race {profile.race.category or '-'} #{profile.race.position} "
            f"con {profile.race.points or '-'} puntos"
        )
    if profile.partners:
        print("Parejas utilizadas: " + ", ".join(sorted(profile.partners)))
    else:
        print("Parejas utilizadas: -")
    print("Partidos disputados:")
    for match in profile.matches:
        print(format_match_line(profile.name, match))
    print("=" * 80)


def print_tournament_summary(tournaments: Iterable[Tournament]) -> None:
    for tournament in tournaments:
        start = _format_date(tournament.start_date)
        end = _format_date(tournament.end_date)
        print(
            f"- {tournament.name} ({start} - {end})"
            + (f" — {tournament.location}" if tournament.location else "")
        )


def _format_date(value: datetime | None) -> str:
    if not value:
        return "Fecha desconocida"
    return value.strftime("%d-%m-%Y")


def main() -> None:
    parser = argparse.ArgumentParser(description="Consulta datos de Premier Padel 2025")
    parser.add_argument("--year", type=int, default=2025, help="Año del calendario a consultar")
    parser.add_argument(
        "--log", default="WARNING", help="Nivel de log (DEBUG, INFO, WARNING, ERROR)"
    )
    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log.upper(), logging.WARNING))

    client = FIPPadelClient()

    logger.info("Descargando torneos Premier Padel del %s", args.year)
    tournaments = client.get_premier_padel_tournaments(args.year)
    print(f"Se encontraron {len(tournaments)} torneos de Premier Padel en {args.year}.")
    print("Torneos disponibles:")
    print_tournament_summary(tournaments)

    logger.info("Descargando rankings y race")
    rankings = client.get_rankings()
    index = build_player_index(tournaments, rankings)

    print("\nEscribe parte del nombre del jugador para consultarlo.")
    print("Comandos disponibles: 'lista' para ver todos, 'salir' para finalizar.")

    while True:
        try:
            raw = input("Jugador: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSaliendo...")
            break

        if not raw:
            continue
        if raw.lower() in {"salir", "exit", "quit"}:
            print("Hasta pronto!")
            break
        if raw.lower() == "lista":
            for profile in index.all():
                print(profile.summary())
            continue

        matches = index.search(raw)
        if not matches:
            print("No se encontraron jugadores con ese nombre.")
            continue
        if len(matches) > 1:
            print("Se encontraron varias coincidencias, elige una opción exacta:")
            for profile in matches:
                print(" - " + profile.summary())
            exact = index.get(raw.lower())
            if exact:
                show_player_detail(exact)
            continue

        show_player_detail(matches[0])


if __name__ == "__main__":
    main()
