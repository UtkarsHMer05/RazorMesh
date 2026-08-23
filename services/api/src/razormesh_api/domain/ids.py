"""Strongly typed, validated identifiers.

Format: ``<prefix>_<26 chars Crockford-base32 ULID>``, e.g.
``intent_01ARZ3NDEKTSV4RRFFQ69G5FAV``. Identifiers are immutable, hashable and
validated on construction — arbitrary strings can never masquerade as domain
identities. Cross-type equality is intentionally impossible.
"""

import re
import secrets
import time
from typing import Final

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

_CROCKFORD: Final = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LEN: Final = 26
_ULID_RE: Final = re.compile(rf"^[{_CROCKFORD}]{{{_ULID_LEN}}}$")


class IdentifierError(ValueError):
    """Raised when an identifier string is malformed."""


def new_ulid() -> str:
    """Sortable unique identifier: 48-bit millisecond timestamp + 80 random bits."""
    value = (time.time_ns() // 1_000_000 << 80) | int.from_bytes(secrets.token_bytes(10), "big")
    return "".join(
        _CROCKFORD[(value >> (shift * 5)) & 0x1F] for shift in range(_ULID_LEN - 1, -1, -1)
    )


def _validate_raw(prefix: str, raw: str) -> str:
    expected_len = len(prefix) + 1 + _ULID_LEN
    if not raw.startswith(f"{prefix}_"):
        raise IdentifierError(f"malformed {prefix} id {raw!r}: must start with '{prefix}_'")
    if len(raw) != expected_len:
        raise IdentifierError(f"malformed {prefix} id {raw!r}: expected {expected_len} characters")
    if not _ULID_RE.fullmatch(raw[len(prefix) + 1 :]):
        raise IdentifierError(f"malformed {prefix} id {raw!r}: invalid character set")
    return raw


class Identifier:
    """Base class for typed identifiers; concrete types declare PREFIX + generate()."""

    PREFIX: str = ""
    _value: str

    __slots__ = ("_value",)

    def __init__(self, raw: str) -> None:
        object.__setattr__(self, "_value", _validate_raw(self.PREFIX, raw))

    @classmethod
    def generate(cls) -> "Identifier":
        raise NotImplementedError("concrete identifier types must implement generate()")

    @property
    def value(self) -> str:
        return self._value

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        _ = source_type
        def _serialize(inst: "Identifier") -> str:
            return inst.value

        inner = core_schema.union_schema(
            [core_schema.is_instance_schema(cls), core_schema.str_schema()]
        )
        return core_schema.no_info_after_validator_function(
            cls._pydantic_validate,
            inner,
            serialization=core_schema.plain_serializer_function_ser_schema(_serialize),
        )

    @classmethod
    def _pydantic_validate(cls, value: object) -> "Identifier":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(value)
        raise IdentifierError(f"invalid {cls.PREFIX} identifier: {value!r}")

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("identifiers are immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("identifiers are immutable")

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._value!r})"

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and other._value == self._value

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._value))


class IntentId(Identifier):
    PREFIX = "intent"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "IntentId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


class CheckoutId(Identifier):
    PREFIX = "chk"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "CheckoutId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


class DecisionId(Identifier):
    PREFIX = "dec"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "DecisionId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


class ExecutionTicketId(Identifier):
    PREFIX = "tk"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "ExecutionTicketId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


class MerchantId(Identifier):
    PREFIX = "mrc"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "MerchantId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


class ProductId(Identifier):
    PREFIX = "prd"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "ProductId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


class PaymentId(Identifier):
    PREFIX = "pay"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "PaymentId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


class AuditEventId(Identifier):
    PREFIX = "evt"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "AuditEventId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


class PrincipalId(Identifier):
    PREFIX = "usr"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "PrincipalId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


class AgentId(Identifier):
    PREFIX = "agt"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "AgentId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


class ExecutionAttemptId(Identifier):
    PREFIX = "exa"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "ExecutionAttemptId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


class ReservationId(Identifier):
    PREFIX = "res"
    __slots__ = ()

    @classmethod
    def generate(cls) -> "ReservationId":
        return cls(f"{cls.PREFIX}_{new_ulid()}")


ALL_ID_TYPES: Final[tuple[type[Identifier], ...]] = (
    IntentId,
    CheckoutId,
    DecisionId,
    ExecutionTicketId,
    MerchantId,
    ProductId,
    PaymentId,
    AuditEventId,
    PrincipalId,
    AgentId,
    ExecutionAttemptId,
    ReservationId,
)
