"""M16 acceptance: Money value object invariants + Hypothesis properties."""

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from razormesh_api.domain.money import MAX_AMOUNT_MINOR, Money, MoneyError


def test_499900_inr() -> None:
    m = Money(499900)
    assert m.amount_minor == 499900
    assert m.currency == "INR"
    assert m.display() == "INR 4999.00"


def test_zero_money() -> None:
    assert Money.zero().is_zero()
    assert Money(0).display() == "INR 0.00"


def test_float_rejected_loudly() -> None:
    for bad in (10.5, 100.0):
        with pytest.raises(MoneyError):
            Money(bad)  # type: ignore[arg-type]
        with pytest.raises(MoneyError):
            Money(Decimal("10.5"))


def test_integral_decimal_accepted() -> None:
    assert Money(Decimal("499900")).amount_minor == 499900


@pytest.mark.parametrize("bad", [-1, -499900])
def test_negative_rejected(bad: int) -> None:
    with pytest.raises(MoneyError):
        Money(bad)


def test_bool_rejected() -> None:
    with pytest.raises(MoneyError):
        Money(True)  # type: ignore[arg-type]


def test_currency_mismatch_forbidden() -> None:
    inr = Money(500)
    usd = Money(500, "USD")
    with pytest.raises(MoneyError, match="currency mismatch"):
        inr.add(usd)
    with pytest.raises(MoneyError, match="currency mismatch"):
        _ = inr < usd
    with pytest.raises(MoneyError, match="currency mismatch"):
        inr.subtract(usd)


def test_unknown_currency_rejected() -> None:
    with pytest.raises(MoneyError):
        Money(1, "inr")  # lowercase rejected: canonical ISO-style codes only
    with pytest.raises(MoneyError):
        Money(1, "XYZQ")


def test_safe_arithmetic_and_boundaries() -> None:
    a = Money(300000)
    b = Money(200000)
    assert a.add(b) == Money(500000)
    assert a.add(b).subtract(b) == a
    assert a.multiply_positive_int(3) == Money(900000)

    big = MAX_AMOUNT_MINOR
    assert Money(big).add(Money(0)) == Money(big)
    with pytest.raises(MoneyError):
        Money(big).add(Money(1))
    with pytest.raises(MoneyError):
        Money(0).subtract(Money(1))
    with pytest.raises(MoneyError):
        Money(MAX_AMOUNT_MINOR).multiply_positive_int(2)


def test_ordering() -> None:
    small = Money(1000)
    large = Money(2000)
    assert small < large
    assert small <= Money(1000)
    assert large > small >= small
    assert not (Money(1000, "USD") == Money(1000))  # different currency != equal


# ---------------------------------------------------------------------------
# Hypothesis property tests (deterministic CI profile)
# ---------------------------------------------------------------------------

amounts = st.integers(min_value=0, max_value=MAX_AMOUNT_MINOR // 2)
# Three-way sums must stay within the sanity bound to exercise pure arithmetic.
small_amounts = st.integers(min_value=0, max_value=MAX_AMOUNT_MINOR // 8)


@settings(max_examples=200, deadline=None)
@given(st.data())
def test_addition_commutative(data) -> None:  # type: ignore[no-untyped-def]
    a = data.draw(amounts)
    b = data.draw(amounts)
    assert Money(a).add(Money(b)) == Money(b).add(Money(a))


@settings(max_examples=200, deadline=None)
@given(st.data())
def test_associativity_within_bounds(data) -> None:  # type: ignore[no-untyped-def]
    a = data.draw(small_amounts)
    b = data.draw(small_amounts)
    c = data.draw(small_amounts)
    left = Money(a).add(Money(b)).add(Money(c))
    right = Money(a).add(Money(b).add(Money(c)))
    assert left == right


@settings(max_examples=100, deadline=None)
@given(amounts)
def test_never_negative(a: int) -> None:
    m = Money(a)
    assert m.amount_minor >= 0
    if a > 0:
        with pytest.raises(MoneyError):
            m.subtract(m.add(Money(1)))


@settings(max_examples=100, deadline=None)
@given(st.data())
def test_subtract_roundtrip(data) -> None:  # type: ignore[no-untyped-def]
    a = data.draw(amounts)
    b = data.draw(st.integers(min_value=0, max_value=a))
    assert Money(a).subtract(Money(b)).add(Money(b)) == Money(a)
