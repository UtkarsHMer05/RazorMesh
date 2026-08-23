"""M35: atomic nonce claim via Redis — coordination ONLY, never durable truth.

The first execution attempt to claim a ticket's nonce wins; every later attempt
with the same nonce is rejected. This makes single-use enforcement safe under
concurrency while PostgreSQL remains the durable financial authority.

Fail-closed: if Redis cannot answer, claiming raises ``CoordinationUnavailable``
— callers must NOT proceed with a side effect they could not de-duplicate.
"""

import uuid

from redis import Redis


class NonceError(Exception):
    pass


class NonceAlreadyClaimed(NonceError):
    def __init__(self, nonce: str) -> None:
        super().__init__(f"nonce already claimed: {nonce[:12]}...")
        self.nonce = nonce


class CoordinationUnavailable(NonceError):
    def __init__(self, detail: str) -> None:
        super().__init__(f"nonce coordination unavailable: {detail}")


_KEY_PREFIX = "razormesh:nonce:"


class NonceRegistry:
    def __init__(self, client: Redis, ttl_seconds: int = 300) -> None:
        self._client = client
        self._ttl = ttl_seconds

    @staticmethod
    def _key(nonce: str) -> str:
        return f"{_KEY_PREFIX}{nonce}"

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception as exc:
            raise CoordinationUnavailable(f"{type(exc).__name__}: {exc}") from exc

    def claim(self, nonce: str, holder_id: str | None = None) -> str:
        """Atomically claim ``nonce``. Returns the winning holder id.

        Raises NonceAlreadyClaimed on replay. Fails closed when Redis is down.
        """
        holder = holder_id or uuid.uuid4().hex
        key = self._key(nonce)
        try:
            # SET key value NX EX ttl: single atomic compare-and-set.
            acquired = self._client.set(key, holder, nx=True, ex=self._ttl)
        except Exception as exc:
            raise CoordinationUnavailable(f"{type(exc).__name__}: {exc}") from exc
        if not acquired:
            raise NonceAlreadyClaimed(nonce)
        return holder

    def holder_of(self, nonce: str) -> str | None:
        try:
            value = self._client.get(self._key(nonce))
        except Exception as exc:
            raise CoordinationUnavailable(f"{type(exc).__name__}: {exc}") from exc
        return None if value is None else str(value)

    def ttl_of(self, nonce: str) -> int:
        try:
            return int(self._client.ttl(self._key(nonce)))
        except Exception as exc:
            raise CoordinationUnavailable(f"{type(exc).__name__}: {exc}") from exc

    def release(self, nonce: str, holder_id: str) -> None:
        """Compensating release (e.g., pre-execution validation failed).

        Only the current holder may release; compare-and-delete is done via a
        Lua script to stay atomic.
        """
        script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end"
        )
        try:
            self._client.eval(script, 1, self._key(nonce), holder_id)
        except Exception as exc:
            raise CoordinationUnavailable(f"{type(exc).__name__}: {exc}") from exc
