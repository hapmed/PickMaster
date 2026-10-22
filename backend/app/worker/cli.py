"""CLI del worker: ingesta, picks y evaluación desde terminal.

Uso:
    uv run python -m app.worker.cli init-db
    uv run python -m app.worker.cli seed-demo
    uv run python -m app.worker.cli load-csv --dir data
    uv run python -m app.worker.cli generate-picks --match 12
    uv run python -m app.worker.cli evaluate --match 12
    uv run python -m app.worker.cli report --match 12
"""

from __future__ import annotations

import argparse
import logging

from app.db import create_all, new_session, setup_engine
from app.ingestion import csv_loader, demo_seed
from app.models import Match, Player
from app.projection.picks import generate_picks
from app.services import evaluation

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("worker")


def cmd_init_db(_args: argparse.Namespace) -> None:
    create_all(setup_engine())
    logger.info("Esquema creado")


def cmd_seed_demo(args: argparse.Namespace) -> None:
    create_all(setup_engine())
    session = new_session()()
    try:
        counts = demo_seed.seed_demo(
            session, finished=args.finished, upcoming=args.upcoming
        )
        print(f"Semilla demo: {counts}")
    finally:
        session.close()


def cmd_load_csv(args: argparse.Namespace) -> None:
    print(f"Cargados: {csv_loader.load_all(args.dir)}")


def cmd_generate_picks(args: argparse.Namespace) -> None:
    session = new_session()()
    try:
        match = session.get(Match, args.match)
        if match is None:
            raise SystemExit(f"partido {args.match} inexistente")
        picks = generate_picks(session, match)
        session.commit()
        for p in picks:
            player = session.get(Player, p.player_id)
            print(
                f"[{p.position}] {player.name if player else p.player_id}: "
                f"esp {p.expected_points:.1f} pts · P(>=target) {p.probability:.0%} · "
                f"confianza {p.confidence:.0%} · {p.reason}"
            )
    finally:
        session.close()


def cmd_evaluate(args: argparse.Namespace) -> None:
    session = new_session()()
    try:
        out = evaluation.evaluate_match(session, args.match)
        session.commit()
        print(out)
    finally:
        session.close()


def cmd_report(args: argparse.Namespace) -> None:
    session = new_session()()
    try:
        print(evaluation.report_message(session, args.match))
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser("pickmaster-worker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db").set_defaults(func=cmd_init_db)
    seed = sub.add_parser("seed-demo")
    seed.add_argument("--finished", type=int, default=8)
    seed.add_argument("--upcoming", type=int, default=1)
    seed.set_defaults(func=cmd_seed_demo)
    csv_cmd = sub.add_parser("load-csv")
    csv_cmd.add_argument("--dir", default="data")
    csv_cmd.set_defaults(func=cmd_load_csv)
    gen = sub.add_parser("generate-picks")
    gen.add_argument("--match", type=int, required=True)
    gen.set_defaults(func=cmd_generate_picks)
    ev = sub.add_parser("evaluate")
    ev.add_argument("--match", type=int, required=True)
    ev.set_defaults(func=cmd_evaluate)
    rep = sub.add_parser("report")
    rep.add_argument("--match", type=int, required=True)
    rep.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
