"""CLI entrypoint: ``python -m ingest.seed_fighters``.

Loads ``data/fighters_seed.json`` into the ``fighters`` table. Idempotent —
reruns update existing rows in place (matches the upsert pattern in db.py).
"""

from __future__ import annotations

import logging

from .db import Repository, get_conn
from .entities import load_roster

log = logging.getLogger("fighter_pulse")


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    repo = Repository(get_conn())
    roster = load_roster()

    for fighter in roster:
        repo.upsert_fighter(
            slug=str(fighter["slug"]),
            full_name=str(fighter["full_name"]),
            aliases=[str(a) for a in fighter["aliases"]],  # type: ignore[union-attr]
        )

    log.info("fighters_seeded count=%d", len(roster))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
