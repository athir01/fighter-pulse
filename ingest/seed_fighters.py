"""CLI entrypoint: ``python -m ingest.seed_fighters``.

Loads ``data/fighters_seed.json`` into the ``fighters`` table. Idempotent —
reruns update existing rows in place. ``ingest.run`` also does this at startup,
so this is only needed to refresh the roster without running an ingest.
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
        repo.upsert_fighter(fighter["slug"], fighter["full_name"], fighter["aliases"])

    log.info("fighters_seeded count=%d", len(roster))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
