import logging
import os
import time
from collections import deque

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    RetryError,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.football-data.org/v4"
RATE_LIMIT = 10  # requests per minute
WINDOW = 60.0   # seconds


class FootballDataClient:
    """HTTP client for football-data.org API v4.

    Enforces ≤10 requests/minute via a sliding-window counter and retries
    transient failures (HTTP 5xx, connection errors, timeouts) up to 3 times
    with exponential backoff. On permanent failure the error is logged and the
    caller receives None so the pipeline can skip the record without aborting.
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ["FOOTBALL_DATA_API_KEY"]
        self._timestamps: deque[float] = deque()
        self._session = requests.Session()
        self._session.headers.update({"X-Auth-Token": self._api_key})

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        now = time.monotonic()
        # Evict timestamps older than the window
        while self._timestamps and now - self._timestamps[0] >= WINDOW:
            self._timestamps.popleft()
        if len(self._timestamps) >= RATE_LIMIT:
            sleep_for = WINDOW - (now - self._timestamps[0])
            if sleep_for > 0:
                logger.debug("Rate limit reached; sleeping %.1fs", sleep_for)
                time.sleep(sleep_for)
        self._timestamps.append(time.monotonic())

    # ------------------------------------------------------------------
    # Core request with retry
    # ------------------------------------------------------------------

    def get(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Fetch *endpoint* and return parsed JSON, or None on permanent failure."""
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        try:
            return self._get_with_retry(url, params or {})
        except RetryError:
            logger.error("Permanent failure after retries: %s params=%s", url, params)
            return None

    @retry(
        retry=retry_if_exception_type(
            (requests.ConnectionError, requests.Timeout, requests.HTTPError)
        ),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=False,
    )
    def _get_with_retry(self, url: str, params: dict) -> dict:
        self._wait_for_rate_limit()
        response = self._session.get(url, params=params, timeout=30)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning("HTTP 429; sleeping %ds", retry_after)
            time.sleep(retry_after)
            raise requests.HTTPError(response=response)
        if response.status_code >= 500:
            raise requests.HTTPError(response=response)
        response.raise_for_status()
        return response.json()
