"""RSS-feed news source — the free, no-ToS-risk ingestion path.

Free and purpose-built for programmatic consumption (unlike scraping HTML),
so this is the source to extend first if more outlets are added.

Failure isolation: a dead feed or a malformed entry is logged and skipped.
This matters because ``discover`` is a generator — an exception raised here
surfaces in the caller's ``for`` statement, *outside* its per-article
try/except, and would abort the whole run.
"""

from __future__ import annotations

import calendar
import logging
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import feedparser

from ..models import ParsedArticle
from .base import NewsSource

log = logging.getLogger("fighter_pulse")

FEEDS: dict[str, str] = {
    "mmafighting": "https://www.mmafighting.com/rss/index.xml",
    "sherdog": "https://www.sherdog.com/rss/news.xml",
    "bjpenn": "https://www.bjpenn.com/feed/",
}


def _published_at(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    # feedparser returns a UTC struct_time; timegm interprets it as UTC.
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)


class RssSource(NewsSource):
    source_name = "rss"

    def __init__(
        self,
        feeds: dict[str, str] | None = None,
        *,
        user_agent: str = "fighter-pulse/0.1",
        rate_limit_rps: float = 1.0,
    ) -> None:
        self.feeds = feeds if feeds is not None else FEEDS
        self.user_agent = user_agent
        self._min_interval = 1.0 / rate_limit_rps if rate_limit_rps > 0 else 0.0

    def discover(self) -> Iterator[ParsedArticle]:
        for i, (outlet, feed_url) in enumerate(self.feeds.items()):
            if i and self._min_interval:
                time.sleep(self._min_interval)
            parsed = feedparser.parse(feed_url, agent=self.user_agent)
            if parsed.get("bozo") and not parsed.entries:
                log.error("feed_failed outlet=%s error=%r", outlet, parsed.get("bozo_exception"))
                continue
            for entry in parsed.entries:
                link = entry.get("link")
                title = entry.get("title")
                if not link or not title:
                    log.warning("entry_skipped outlet=%s reason=missing_link_or_title", outlet)
                    continue
                yield ParsedArticle(
                    source=f"rss:{outlet}",
                    guid=entry.get("id") or link,
                    url=link,
                    title=title,
                    summary=entry.get("summary"),
                    published_at=_published_at(entry),
                )
