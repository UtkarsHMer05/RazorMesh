"""M35 acceptance: atomic nonce claim; replay rejection; >=20-worker race."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from redis import Redis

from razormesh_api.nonce import (
    CoordinationUnavailable,
    NonceAlreadyClaimed,
    NonceRegistry,
)

WORKERS = 20


def _redis() -> Redis:
    url = os.environ.get("RAZORMESH_TEST_REDIS_URL", "redis://127.0.0.1:16379/0")
    return Redis.from_url(url, decode_responses=True)


@pytest.fixture()
def registry():
    r = NonceRegistry(_redis(), ttl_seconds=120)
    assert r.ping()
    yield r


def test_first_claim_wins_replay_rejected(registry: NonceRegistry) -> None:
    nonce = uuid.uuid4().hex + uuid.uuid4().hex
    holder = registry.claim(nonce, "attempt-1")
    assert holder == "attempt-1"

    with pytest.raises(NonceAlreadyClaimed):
        registry.claim(nonce, "attempt-2")

    # distinct nonce claims independently (no cross-talk)
    other = uuid.uuid4().hex + uuid.uuid4().hex
    assert registry.claim(other, "attempt-3")


def test_claim_has_ttl_not_permanent(registry: NonceRegistry) -> None:
    nonce = uuid.uuid4().hex + uuid.uuid4().hex
    registry.claim(nonce, "h")
    ttl = registry.ttl_of(nonce)
    assert 0 < ttl <= 120


def test_only_holder_can_release(registry: NonceRegistry) -> None:
    nonce = uuid.uuid4().hex + uuid.uuid4().hex
    holder = registry.claim(nonce, "holder-A")
    registry.release(nonce, "not-the-holder")  # no-op: wrong holder
    with pytest.raises(NonceAlreadyClaimed):
        registry.claim(nonce, "challenger")

    registry.release(nonce, holder)  # correct holder frees it
    assert registry.claim(nonce, "new-attempt")


def test_twenty_worker_same_nonce_race_exactly_one_winner(
    registry: NonceRegistry,
) -> None:
    """Real many-worker race on ONE ticket nonce: exactly 1 effect."""
    nonce = uuid.uuid4().hex + uuid.uuid4().hex

    def worker(i: int) -> str:
        try:
            return f"winner:{registry.claim(nonce, f'worker-{i}')}"
        except NonceAlreadyClaimed:
            return "rejected"

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(worker, range(WORKERS)))

    winners = [r for r in results if r.startswith("winner:")]
    rejected = [r for r in results if r == "rejected"]
    assert len(winners) == 1, winners
    assert len(rejected) == WORKERS - 1


def test_unavailable_redis_fails_closed() -> None:
    broken = NonceRegistry(
        Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=1), ttl_seconds=60
    )
    with pytest.raises(CoordinationUnavailable):
        broken.ping()
    with pytest.raises(CoordinationUnavailable):
        broken.claim(uuid.uuid4().hex + uuid.uuid4().hex)
