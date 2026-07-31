"""Per-domain rate limiter for web scraping."""

from __future__ import annotations

import threading
import time
from urllib.parse import urlparse


class DomainRateLimiter:
    """Thread-safe per-domain rate limiter.

    Tracks the last request time for each domain and ensures a minimum
    interval between consecutive requests to the same domain.

    Usage::

        limiter = DomainRateLimiter(default_interval=1.0)
        limiter.wait("https://example.com/page1")
        # ... make request ...
        limiter.wait("https://example.com/page2")
        # blocks until 1.0s has elapsed since the first request
    """

    def __init__(self, default_interval: float = 1.0) -> None:
        self._default_interval = default_interval
        self._last_request: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, url: str, interval: float | None = None) -> None:
        """Block until enough time has passed since the last request to this domain."""
        domain = urlparse(url).netloc.lower()
        wait_seconds = interval if interval is not None else self._default_interval

        with self._lock:
            last = self._last_request.get(domain, 0.0)
            elapsed = time.monotonic() - last
            if elapsed < wait_seconds:
                time.sleep(wait_seconds - elapsed)
            self._last_request[domain] = time.monotonic()
