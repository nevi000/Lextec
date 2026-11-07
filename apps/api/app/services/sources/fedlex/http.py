"""Safe, polite HTTP access to Fedlex.

Security properties (all enforced here, in one place):
* only https and only hosts from the allowlist (SSRF protection); no arbitrary download URLs;
* TLS certificate verification stays on;
* redirects are followed manually (max 3) and only to allowed hosts;
* response size is capped while streaming;
* timeouts, bounded concurrency, minimum request interval, bounded retries with backoff.
Requests carry only public statute references; never case data.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import Settings

USER_AGENT = "LexTecBridge/0.1 (research prototype; fetches public Swiss federal law)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class FedlexError(Exception):
    """Base class; ``code`` is stored in the sync state."""

    code = "ERROR"


class FedlexDisabled(FedlexError):
    code = "DISABLED"


class FedlexNetworkError(FedlexError):
    code = "NETWORK_ERROR"


class FedlexHttpError(FedlexError):
    code = "HTTP_ERROR"

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class FedlexForbiddenUrl(FedlexError):
    code = "FORBIDDEN_URL"


class FedlexTooLarge(FedlexError):
    code = "RESPONSE_TOO_LARGE"


class FedlexBadResponse(FedlexError):
    code = "BAD_RESPONSE"


class FedlexHttp:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._s = settings
        self._sleep = sleep
        self._clock = clock
        self._sem = threading.BoundedSemaphore(max(1, settings.fedlex_max_concurrent_requests))
        self._rate_lock = threading.Lock()
        self._last_request = 0.0
        self.request_count = 0
        self._client = httpx.Client(
            timeout=settings.fedlex_timeout_seconds,
            follow_redirects=False,
            verify=True,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )

    # ---- url safety ------------------------------------------------------------------------
    def check_url(self, url: str) -> str:
        p = urlparse(url)
        if p.scheme != "https":
            raise FedlexForbiddenUrl(f"Nur https erlaubt: {url[:80]}")
        host = (p.hostname or "").lower()
        if host not in {h.lower() for h in self._s.fedlex_allowed_hosts}:
            raise FedlexForbiddenUrl(f"Host nicht erlaubt: {host}")
        if p.username or p.password:
            raise FedlexForbiddenUrl("Zugangsdaten in der URL nicht erlaubt.")
        return url

    # ---- core request ------------------------------------------------------------------------
    def _throttle(self) -> None:
        with self._rate_lock:
            wait = self._s.fedlex_min_request_interval_seconds - (
                self._clock() - self._last_request
            )
            if wait > 0:
                self._sleep(wait)
            self._last_request = self._clock()

    def _once(
        self, method: str, url: str, *, data: dict | None, accept: str, max_bytes: int
    ) -> bytes:
        current = self.check_url(url)
        for _hop in range(4):
            with self._sem:
                self._throttle()
                self.request_count += 1
                try:
                    with self._client.stream(
                        method,
                        current,
                        data=data if method == "POST" else None,
                        headers={"Accept": accept},
                    ) as resp:
                        if resp.status_code in (301, 302, 303, 307, 308):
                            loc = resp.headers.get("location")
                            if not loc:
                                raise FedlexBadResponse("Redirect ohne Location.")
                            current = self.check_url(urljoin(current, loc))
                            method, data = "GET", None
                            continue
                        if resp.status_code >= 400:
                            raise FedlexHttpError(
                                resp.status_code,
                                f"HTTP {resp.status_code} von {urlparse(current).path[:60]}",
                            )
                        declared = resp.headers.get("content-length")
                        if declared and declared.isdigit() and int(declared) > max_bytes:
                            raise FedlexTooLarge(f"Antwort zu gross ({declared} Bytes).")
                        chunks: list[bytes] = []
                        total = 0
                        for chunk in resp.iter_bytes():
                            total += len(chunk)
                            if total > max_bytes:
                                raise FedlexTooLarge(f"Antwort überschreitet {max_bytes} Bytes.")
                            chunks.append(chunk)
                        return b"".join(chunks)
                except httpx.TimeoutException as exc:
                    raise FedlexNetworkError("Zeitüberschreitung bei Fedlex.") from exc
                except httpx.TransportError as exc:
                    raise FedlexNetworkError(f"Netzwerkfehler: {type(exc).__name__}") from exc
        raise FedlexBadResponse("Zu viele Weiterleitungen.")

    def request(
        self,
        method: str,
        url: str,
        *,
        data: dict | None = None,
        accept: str = "*/*",
        max_bytes: int | None = None,
    ) -> bytes:
        if not self._s.fedlex_enabled:
            raise FedlexDisabled("Fedlex ist deaktiviert (FEDLEX_ENABLED=false).")
        limit = max_bytes or self._s.fedlex_max_response_bytes
        last: Exception | None = None
        for attempt in range(self._s.fedlex_max_retries + 1):
            try:
                return self._once(method, url, data=data, accept=accept, max_bytes=limit)
            except FedlexHttpError as exc:
                last = exc
                if exc.status not in RETRY_STATUS or attempt >= self._s.fedlex_max_retries:
                    raise
            except FedlexNetworkError as exc:
                last = exc
                if attempt >= self._s.fedlex_max_retries:
                    raise
            self._sleep(min(2**attempt, 8) * 0.5)  # backoff
        raise last or FedlexNetworkError("Unbekannter Fehler")

    # ---- convenience --------------------------------------------------------------------------
    def sparql(self, query: str) -> list[dict[str, str]]:
        """POST a SPARQL SELECT to the official endpoint; returns plain {var: value} rows."""
        import json

        raw = self.request(
            "POST",
            self._s.fedlex_sparql_url,
            data={"query": query},
            accept="application/sparql-results+json",
            max_bytes=5_000_000,
        )
        try:
            bindings = json.loads(raw)["results"]["bindings"]
            return [{k: v["value"] for k, v in row.items()} for row in bindings]
        except (ValueError, KeyError, TypeError) as exc:
            raise FedlexBadResponse("Unerwartete SPARQL-Antwort (kein JSON-Ergebnis).") from exc

    def get_document(self, url: str) -> bytes:
        p = urlparse(url)
        if not p.path.startswith("/filestore/"):
            raise FedlexForbiddenUrl("Dokument-URLs müssen unter /filestore/ liegen.")
        return self.request("GET", url, accept="application/xml")

    def close(self) -> None:
        self._client.close()
