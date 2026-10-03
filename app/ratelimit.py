"""In-memory rate limits.

Good enough for one or two replicas; the Azure OpenAI deployment's
tokens-per-minute quota is the hard ceiling.

- `limiter`: public questions, per IP per minute and per day, plus a global daily cap.
- `staff_limiter`: signed-in staff skip the public limits and get their own
  per-user limit instead (STAFF_RATE_LIMIT_PER_MINUTE, default 60).
- `login_limiter`: staff login attempts per IP (10 per 15 minutes).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request

from . import config


def _trim(q: deque, window: float, now: float) -> None:
    while q and now - q[0] > window:
        q.popleft()


class RateLimiter:
    """Public limits. Limits are read from config at check time unless given."""

    def __init__(self, per_minute: int | None = None, per_day: int | None = None, global_per_day: int | None = None):
        self._per_minute = per_minute
        self._per_day = per_day
        self._global_per_day = global_per_day
        self.minute: dict[str, deque] = defaultdict(deque)
        self.day: dict[str, deque] = defaultdict(deque)
        self.global_day: deque = deque()

    def check(self, ip: str) -> str | None:
        per_minute = self._per_minute if self._per_minute is not None else config.PER_IP_PER_MINUTE
        per_day = self._per_day if self._per_day is not None else config.PER_IP_PER_DAY
        global_per_day = self._global_per_day if self._global_per_day is not None else config.GLOBAL_PER_DAY
        now = time.time()
        m, d, g = self.minute[ip], self.day[ip], self.global_day
        _trim(m, 60, now)
        _trim(d, 86400, now)
        _trim(g, 86400, now)
        if len(g) >= global_per_day:
            return "The assistant has reached its daily question limit. Please try again tomorrow."
        if len(d) >= per_day:
            return "You have reached the daily question limit. Please try again tomorrow."
        if len(m) >= per_minute:
            return "Too many questions in a short time. Please wait a minute and try again."
        m.append(now)
        d.append(now)
        g.append(now)
        if len(self.day) > 50_000:  # drop idle clients so memory stays bounded
            for k in [k for k, v in self.day.items() if not v][:10_000]:
                self.day.pop(k, None)
                self.minute.pop(k, None)
        return None

    def reset(self) -> None:
        self.minute.clear()
        self.day.clear()
        self.global_day.clear()


class WindowLimiter:
    """N events per key per sliding window."""

    def __init__(self, limit: int | None, window: float | None, message: str, limit_attr: str = "", window_attr: str = ""):
        self._limit, self._window = limit, window
        self._limit_attr, self._window_attr = limit_attr, window_attr
        self.message = message
        self.hits: dict[str, deque] = defaultdict(deque)

    @property
    def limit(self) -> int:
        return self._limit if self._limit is not None else getattr(config, self._limit_attr)

    @property
    def window(self) -> float:
        return self._window if self._window is not None else getattr(config, self._window_attr)

    def check(self, key: str) -> str | None:
        now = time.time()
        q = self.hits[key]
        _trim(q, self.window, now)
        if len(q) >= self.limit:
            return self.message
        q.append(now)
        if len(self.hits) > 10_000:
            for k in [k for k, v in self.hits.items() if not v][:5_000]:
                self.hits.pop(k, None)
        return None

    def reset(self) -> None:
        self.hits.clear()


limiter = RateLimiter()
staff_limiter = WindowLimiter(
    None, 60, "Too many requests in a short time. Please wait a minute and try again.", limit_attr="STAFF_PER_MINUTE"
)
login_limiter = WindowLimiter(
    None,
    None,
    "Too many sign-in attempts. Please wait 15 minutes and try again.",
    limit_attr="LOGIN_ATTEMPTS",
    window_attr="LOGIN_WINDOW_SECONDS",
)


def client_ip(request: Request) -> str:
    # Container Apps ingress appends the real client address as the last
    # X-Forwarded-For entry; earlier entries can be set by the client.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def check_request(request: Request, staff_user: str | None) -> str | None:
    """The limit message for this request, or None. Staff bypass the per-IP limits."""
    if staff_user:
        return staff_limiter.check(staff_user)
    return limiter.check(client_ip(request))


def reset_all() -> None:
    limiter.reset()
    staff_limiter.reset()
    login_limiter.reset()
