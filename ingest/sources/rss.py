"""RSS-feed news source — the free, no-ToS-risk ingestion path.

Free and purpose-built for programmatic consumption (unlike scraping HTML),
so this is the source to extend first if more outlets are added.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

import feedparser

from ..models import ParsedArticle
from .base import NewsSource

FEEDS: dict[str, str] = {
    "mmajunkie": "https://mmajunkie.usatoday.com/feed",
    "mmafighting": "https://www.mmafighting.com/rss/current",
}


class RssSource(NewsSource):
    source_name = "rss"

    def __init__(self, feeds: dict[str, str] | None = None) -> None:
        self.feeds = feeds if feeds is not None else FEEDS

    def discover(self) -> Iterable[ParsedArticle]:
        for outlet, feed_url in self.feeds.items():
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries:
                published_at = None
                if getattr(entry, "published_parsed", None):
                    published_at = datetime(
                        *entry.published_parsed[:6], tzinfo=UTC
                    )
                yield ParsedArticle(
                    source=f"rss:{outlet}",
                    guid=entry.get("id", entry.link),
                    url=entry.link,
                    title=entry.title,
                    summary=entry.get("summary"),
                    published_at=published_at,
                )
