"""Centralised HTTP fetch with retry, exponential backoff, and fail-fast."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter


class ScrapeHTTPError(Exception):
    """Raised when a URL is unreachable after all retry attempts."""

    def __init__(
        self,
        url: str,
        *,
        status_code: int | None = None,
        attempts: int,
        last_error: Exception,
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"Failed to fetch {url} after {attempts} attempts "
            f"(status={status_code}): {last_error}"
        )


def fetch(
    session: Any,
    url: str,
    *,
    timeout: int = 30,
    max_retries: int = 3,
    backoff_base: float = 2.0,
    rate_limiter: DomainRateLimiter | None = None,
    params: dict | None = None,
    method: str = "GET",
    **kwargs: Any,
) -> requests.Response:
    """Fetch a URL with retry and exponential backoff.

    Works with both ``requests.Session`` and ``curl_cffi.requests.Session``.

    Raises ScrapeHTTPError if all attempts are exhausted.
    """
    last_error: Exception | None = None
    status_code: int | None = None

    for attempt in range(max_retries):
        if rate_limiter is not None:
            rate_limiter.wait(url)

        try:
            resp = session.request(
                method, url, timeout=timeout, params=params, **kwargs
            )
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_error = e
            status_code = getattr(getattr(e, "response", None), "status_code", None)
            if attempt < max_retries - 1:
                time.sleep(backoff_base ** (attempt + 1))

    raise ScrapeHTTPError(
        url,
        status_code=status_code,
        attempts=max_retries,
        last_error=last_error,  # type: ignore[arg-type]
    )
