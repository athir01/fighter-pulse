from datetime import UTC, datetime
from typing import Any

import feedparser
import pytest

from ingest.sources.rss import RssSource


class _Feed(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        return self[name]


def test_skips_bad_entries_and_dead_feeds(monkeypatch: pytest.MonkeyPatch) -> None:
    feeds = {
        "good": _Feed(
            bozo=0,
            entries=[
                {
                    "id": "1",
                    "link": "https://x/1",
                    "title": "A",
                    "published_parsed": (2026, 7, 1, 12, 0, 0, 0, 0, 0),
                },
                {"id": "2", "title": "no link"},  # malformed — must not kill the run
            ],
        ),
        "dead": _Feed(bozo=1, bozo_exception=OSError("404"), entries=[]),
    }
    monkeypatch.setattr(feedparser, "parse", lambda url, agent=None: feeds[url])

    source = RssSource({"good": "good", "dead": "dead"}, rate_limit_rps=0)
    articles = list(source.discover())

    assert [a.guid for a in articles] == ["1"]
    assert articles[0].published_at == datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
