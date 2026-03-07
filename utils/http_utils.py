from __future__ import annotations

import logging
import ssl
import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


USER_AGENT = "astro-problems-archive/0.1 (+public archival crawl; contact: local-run)"


@dataclass(slots=True)
class Response:
    url: str
    final_url: str
    status_code: int
    headers: Mapping[str, str]
    content: bytes

    @property
    def text(self) -> str:
        charset = "utf-8"
        content_type = self.headers.get("Content-Type", "")
        if "charset=" in content_type:
            charset = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
        return self.content.decode(charset, errors="replace")


class HttpClient:
    def __init__(
        self,
        *,
        logger: logging.Logger,
        rate_limit_seconds: float = 0.6,
        timeout_seconds: float = 45.0,
        retries: int = 3,
        dry_run: bool = False,
    ) -> None:
        self.logger = logger
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.dry_run = dry_run
        self.last_request_at: dict[str, float] = defaultdict(float)
        self.robot_parsers: dict[str, tuple[urllib.robotparser.RobotFileParser | None, bool]] = {}
        self.ssl_context = ssl.create_default_context()

    def fetch(self, url: str) -> Response:
        if self.dry_run:
            self.logger.info("DRY_RUN fetch %s", url)
            return Response(url=url, final_url=url, status_code=0, headers={}, content=b"")

        self._respect_rate_limit(url)
        self._ensure_allowed_by_robots(url)

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout_seconds,
                    context=self.ssl_context,
                ) as response:
                    final_url = response.geturl()
                    payload = response.read()
                    headers = {key: value for key, value in response.headers.items()}
                    self.logger.info("FETCH ok url=%s status=%s bytes=%s", url, response.status, len(payload))
                    return Response(
                        url=url,
                        final_url=final_url,
                        status_code=response.status,
                        headers=headers,
                        content=payload,
                    )
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
                last_error = error
                self.logger.warning("FETCH retry url=%s attempt=%s error=%s", url, attempt, error)
                time.sleep(min(3.0, attempt * self.rate_limit_seconds))

        assert last_error is not None
        raise last_error

    def _respect_rate_limit(self, url: str) -> None:
        domain = urlparse(url).netloc
        wait_for = self.rate_limit_seconds - (time.time() - self.last_request_at[domain])
        if wait_for > 0:
            time.sleep(wait_for)
        self.last_request_at[domain] = time.time()

    def _ensure_allowed_by_robots(self, url: str) -> None:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self.robot_parsers:
            robot_url = f"{base}/robots.txt"
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(robot_url)
            available = True
            try:
                parser.read()
                self.logger.info("ROBOTS loaded %s", robot_url)
            except Exception as error:  # pragma: no cover - depends on remote servers
                available = False
                self.logger.warning("ROBOTS unavailable %s error=%s", robot_url, error)
            self.robot_parsers[base] = (parser if available else None, available)

        parser, available = self.robot_parsers[base]
        if not available or parser is None:
            return
        if not parser.can_fetch(USER_AGENT, url):
            raise PermissionError(f"Blocked by robots.txt: {url}")
