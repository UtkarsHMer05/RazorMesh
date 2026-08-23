"""Money value object: integer minor units + ISO-style currency.

Invariants (SEC-013, RULES Financial correctness):
- amount_minor is an int; floats are rejected loudly, never silently coerced
- amounts are non-negative for purchase semantics (Phase 1 has no refunds/negatives)
- arithmetic and comparisons require identical currency; no silent FX conversion
"""

from decimal import Decimal
from typing import Any, Final

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

MoneyLike = int | Decimal

# Currencies Phase 1 understands (minor-unit exponents per ISO 4217; display only).
CURRENCY_EXPONENTS: Final[dict[str, int]] = {"INR": 2, "USD": 2, "EUR": 2}
DEFAULT_CURRENCY: Final = "INR"

# Upper sanity bound: ₹10^12 minor units. Guards against accidental absurd values.
MAX_AMOUNT_MINOR: Final[int] = 10**15


class MoneyError(ValueError):
    """Raised on invalid money construction or unsafe operations."""


class Money:
    __slots__ = ("amount_minor", "currency")

    amount_minor: int
    currency: str

    def __init__(self, amount_minor: MoneyLike, currency: str = DEFAULT_CURRENCY) -> None:
        if isinstance(amount_minor, bool) or not isinstance(amount_minor, (int, Decimal)):
            raise MoneyError(
                f"money amount must be int or integral Decimal, got {type(amount_minor).__name__} "
                f"(floating-point money is forbidden)"
            )
        if isinstance(amount_minor, Decimal):
            if not amount_minor.is_finite() or amount_minor != amount_minor.to_integral_value():
                raise MoneyError(f"Decimal amount {amount_minor} is not an integral minor unit")
            amount_minor = int(amount_minor)
        if isinstance(amount_minor, float):  # defensive: float subclasses of int are impossible,
            raise MoneyError("float money is forbidden")  # pragma: no cover

        amount_minor = int(amount_minor)
        if amount_minor < 0:
            raise MoneyError(f"purchase amounts must be non-negative, got {amount_minor}")
        if amount_minor > MAX_AMOUNT_MINOR:
            raise MoneyError(f"amount {amount_minor} exceeds sanity bound {MAX_AMOUNT_MINOR}")

        if not isinstance(currency, str) or currency not in CURRENCY_EXPONENTS:
            supported = sorted(CURRENCY_EXPONENTS)
            raise MoneyError(
                f"unsupported or malformed currency {currency!r}; supported: {supported}"
            )

        self.amount_minor = amount_minor
        self.currency = currency

    # -- factories ---------------------------------------------------------

    @classmethod
    def zero(cls, currency: str = DEFAULT_CURRENCY) -> "Money":
        return cls(0, currency)

    def is_zero(self) -> bool:
        return self.amount_minor == 0

    # -- checked arithmetic -------------------------------------------------

    def _require_same_currency(self, other: "Money", op: str) -> None:
        if not isinstance(other, Money):
            raise MoneyError(f"cannot {op} Money with {type(other).__name__}")
        if other.currency != self.currency:
            raise MoneyError(
                f"currency mismatch: cannot {op} {self.currency} with {other.currency} "
                f"(cross-currency conversion is forbidden in Phase 1)"
            )

    def add(self, other: "Money") -> "Money":
        self._require_same_currency(other, "add")
        total = self.amount_minor + other.amount_minor
        if total > MAX_AMOUNT_MINOR:
            raise MoneyError(
                f"addition overflows sane bound: {self.amount_minor} + {other.amount_minor}"
            )
        return Money(total, self.currency)

    def subtract(self, other: "Money") -> "Money":
        self._require_same_currency(other, "subtract")
        result = self.amount_minor - other.amount_minor
        if result < 0:
            raise MoneyError(
                f"subtraction would go negative: {self.amount_minor} - {other.amount_minor}"
            )
        return Money(result, self.currency)

    def multiply_positive_int(self, factor: int) -> "Money":
        if isinstance(factor, bool) or not isinstance(factor, int) or factor < 0:
            raise MoneyError(f"multiplication requires non-negative int, got {factor!r}")
        product = self.amount_minor * factor
        if product > MAX_AMOUNT_MINOR:
            raise MoneyError(f"multiplication overflows sane bound: {factor} x {self.amount_minor}")
        return Money(product, self.currency)

    # -- comparisons --------------------------------------------------------

    def compare(self, other: "Money") -> int:
        """-1 / 0 / +1 against another Money of the same currency."""
        self._require_same_currency(other, "compare")
        if self.amount_minor < other.amount_minor:
            return -1
        if self.amount_minor > other.amount_minor:
            return 1
        return 0

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Money)
            and self.amount_minor == other.amount_minor
            and self.currency == other.currency
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.compare(other) < 0

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.compare(other) <= 0

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.compare(other) > 0

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.compare(other) >= 0

    def __hash__(self) -> int:
        return hash((self.amount_minor, self.currency))

    # -- presentation -------------------------------------------------------

    def display(self) -> str:
        exponent = CURRENCY_EXPONENTS[self.currency]
        major = self.amount_minor // (10**exponent)
        minor = self.amount_minor % (10**exponent)
        return f"{self.currency} {major}.{minor:0{exponent}d}"

    def __repr__(self) -> str:
        return f"Money({self.amount_minor}, {self.currency!r})"

    def __str__(self) -> str:
        return f"{self.amount_minor} {self.currency}"

    # -- pydantic integration ----------------------------------------------

    @classmethod
    def _pydantic_validate(cls, value: object) -> "Money":
        if isinstance(value, Money):
            return value
        if isinstance(value, dict):
            amt = value.get("amount_minor")
            if amt is None:
                raise MoneyError("Money dict missing amount_minor")
            cur = value.get("currency", DEFAULT_CURRENCY)
            if not isinstance(cur, str):
                raise MoneyError(f"invalid currency {cur!r}")
            return cls(amt, cur)
        raise MoneyError(f"cannot parse Money from {value!r}")

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        _ = source_type, handler
        inner = core_schema.union_schema(
            [
                core_schema.is_instance_schema(Money),
                core_schema.typed_dict_schema(
                    {
                        "amount_minor": core_schema.typed_dict_field(core_schema.int_schema()),
                        "currency": core_schema.typed_dict_field(
                            core_schema.str_schema(), required=False
                        ),
                    }
                ),
            ]
        )

        def _serialize(inst: Money) -> dict[str, Any]:
            return {"amount_minor": inst.amount_minor, "currency": inst.currency}

        return core_schema.no_info_after_validator_function(
            cls._pydantic_validate,
            inner,
            serialization=core_schema.plain_serializer_function_ser_schema(_serialize),
        )
