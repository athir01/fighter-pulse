"""Common interface every news source implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from ..models import ParsedArticle


class NewsSource(ABC):
    source_name: str

    @abstractmethod
    def discover(self) -> Iterable[ParsedArticle]:
        """Yield every article currently available from this source."""
        raise NotImplementedError
