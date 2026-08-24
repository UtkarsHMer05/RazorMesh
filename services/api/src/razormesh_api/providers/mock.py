"""M37: mock payment provider with scripted failure/event semantics.

Modes (per master prompt):

- SUCCESS                    deterministic success with a synthetic reference
- DEFINITIVE_FAILURE         failure with error code
- TIMEOUT_BEFORE_EFFECT      raises before ANY provider-side state changes
                             -> executor must record PROVIDER_UNKNOWN while the
                             truth is "nothing happened"
- TIMEOUT_AFTER_SUCCESS      records the effect FIRST, then raises
                             -> PROVIDER_UNKNOWN while the truth is "paid"
                             (reconciliation finds the reference)
- DUPLICATE_EVENT            replays an existing effect's reference instead of
                             creating a new one (webhook-style duplication)
- DELAYED_EVENT              returns UNKNOWN immediately; the true outcome is
                             delivered later via ``pending_events``
- OUT_OF_ORDER_EVENT         delivers terminal events BEFORE their creation
                             event to exercise idempotent consumption

The mock keeps a provider-side ``effects`` ledger so tests can prove whether a
financial effect actually exists provider-side — not just what our DB claims.
"""

import threading
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

from razormesh_api.executor import ChargeCommand, ChargeResult, ProviderOutcome


class MockMode(StrEnum):
    SUCCESS = "SUCCESS"
    DEFINITIVE_FAILURE = "DEFINITIVE_FAILURE"
    TIMEOUT_BEFORE_EFFECT = "TIMEOUT_BEFORE_EFFECT"
    TIMEOUT_AFTER_SUCCESS = "TIMEOUT_AFTER_SUCCESS"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    DELAYED_EVENT = "DELAYED_EVENT"
    OUT_OF_ORDER_EVENT = "OUT_OF_ORDER_EVENT"


@dataclass(frozen=True)
class ProviderEvent:
    seq: int
    kind: str  # CREATED | SUCCEEDED | FAILED
    attempt_id: str
    reference: str | None


@dataclass
class MockPaymentProvider:
    """Thread-safe scriptable provider double."""

    mode: MockMode = MockMode.SUCCESS
    failure_code: str = "CARD_DECLINED"
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    calls: int = 0
    _seq: int = 0
    # provider-side truth: attempt_id -> reference for EFFECTUATED payments
    _effects: dict[str, str] = field(default_factory=dict)
    _event_queue: deque[ProviderEvent] = field(default_factory=deque)

    @property
    def effects(self) -> dict[str, str]:
        return dict(self._effects)

    def pending_events(self) -> list[ProviderEvent]:
        """Drain delivered-but-unconsumed events (webhook simulation)."""
        with self._lock:
            out = list(self._event_queue)
            self._event_queue.clear()
        return out

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _reference(self, command: ChargeCommand) -> str:
        return f"mock_{command.execution_attempt_id}_{command.nonce[:8]}"

    def charge(self, command: ChargeCommand) -> ChargeResult:
        self.calls += 1
        ref = self._reference(command)

        if self.mode == MockMode.SUCCESS:
            with self._lock:
                self._effects.setdefault(command.execution_attempt_id, ref)
                self._event_queue.append(
                    ProviderEvent(self._next_seq(), "SUCCEEDED", command.execution_attempt_id, ref)
                )
            return ChargeResult(ProviderOutcome.SUCCEEDED, provider_reference=ref)

        if self.mode == MockMode.DEFINITIVE_FAILURE:
            with self._lock:
                self._event_queue.append(
                    ProviderEvent(self._next_seq(), "FAILED", command.execution_attempt_id, None)
                )
            return ChargeResult(ProviderOutcome.FAILED, error_code=self.failure_code)

        if self.mode == MockMode.TIMEOUT_BEFORE_EFFECT:
            # Nothing provider-side changed; raise like a dead socket.
            raise TimeoutError(f"mock: timeout before effect for {command.execution_attempt_id}")

        if self.mode == MockMode.TIMEOUT_AFTER_SUCCESS:
            # The money MOVED, then the connection died.
            with self._lock:
                self._effects.setdefault(command.execution_attempt_id, ref)
                self._event_queue.append(
                    ProviderEvent(self._next_seq(), "SUCCEEDED", command.execution_attempt_id, ref)
                )
            raise TimeoutError(f"mock: timeout AFTER success for {command.execution_attempt_id}")

        if self.mode == MockMode.DUPLICATE_EVENT:
            # Replay semantics: same logical effect -> same reference, no new effect.
            with self._lock:
                existing = self._effects.get(command.execution_attempt_id)
                if existing is None:
                    self._effects[command.execution_attempt_id] = ref
                    existing = ref
            return ChargeResult(ProviderOutcome.SUCCEEDED, provider_reference=existing)

        if self.mode == MockMode.DELAYED_EVENT:
            # Outcome unknown NOW; the authoritative event arrives later.
            with self._lock:
                self._event_queue.append(
                    ProviderEvent(self._next_seq(), "SUCCEEDED", command.execution_attempt_id, ref)
                )
            return ChargeResult(ProviderOutcome.UNKNOWN)

        if self.mode == MockMode.OUT_OF_ORDER_EVENT:
            # Deliver terminal event BEFORE its creation event.
            with self._lock:
                self._effects.setdefault(command.execution_attempt_id, ref)
                seq_created = self._next_seq()
                seq_done = self._next_seq()
                self._event_queue.append(
                    ProviderEvent(seq_done, "SUCCEEDED", command.execution_attempt_id, ref)
                )
                self._event_queue.append(
                    ProviderEvent(seq_created, "CREATED", command.execution_attempt_id, None)
                )
            return ChargeResult(ProviderOutcome.SUCCEEDED, provider_reference=ref)

        raise ValueError(f"unknown mock mode: {self.mode}")
