"""Provenance/trust metadata: untrusted data may propose, never authorize."""

from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from razormesh_api.clock import SystemClock

T = TypeVar("T")


class TrustClass(StrEnum):
    """How much the system trusts where a value came from."""

    USER_AUTHORITY = "USER_AUTHORITY"  # human-confirmed authorization
    TRUSTED_SYSTEM = "TRUSTED_SYSTEM"  # computed by trusted control plane
    VERIFIED_MERCHANT_DATA = "VERIFIED_MERCHANT_DATA"  # structured catalog facts
    UNTRUSTED_CONTENT = "UNTRUSTED_CONTENT"  # free text / agent output / web
    DERIVED = "DERIVED"  # computed from other provenanced values


class SourceType(StrEnum):
    USER_CONFIRMATION = "USER_CONFIRMATION"
    TRUSTED_SERVICE = "TRUSTED_SERVICE"
    MERCHANT_CATALOG = "MERCHANT_CATALOG"
    AGENT_PROPOSAL = "AGENT_PROPOSAL"
    MERCHANT_FREE_TEXT = "MERCHANT_FREE_TEXT"
    DERIVATION = "DERIVATION"


class TrustViolation(Exception):
    """Raised when untrusted/lower-trust data reaches an authority-typed slot."""


# Which trust classes are acceptable where.
_AUTHORITY_CLASSES: frozenset[TrustClass] = frozenset(
    {TrustClass.USER_AUTHORITY, TrustClass.TRUSTED_SYSTEM}
)


class Provenanced(BaseModel, Generic[T]):  # noqa: UP046 - intentionally generic for Py 3.13
    """A value plus explicit trust metadata. Frozen: provenance cannot be rewritten."""

    model_config = ConfigDict(frozen=True)

    value: T
    trust_class: TrustClass
    source_type: SourceType
    source_id: str
    observed_at: datetime

    @classmethod
    def user_confirmed(cls, value: T, principal_id: str) -> "Provenanced[T]":
        """The ONLY construction path for USER_AUTHORITY provenance."""
        return cls(
            value=value,
            trust_class=TrustClass.USER_AUTHORITY,
            source_type=SourceType.USER_CONFIRMATION,
            source_id=principal_id,
            observed_at=SystemClock().now_utc(),
        )

    @classmethod
    def from_trusted_service(cls, value: T, service_id: str) -> "Provenanced[T]":
        return cls(
            value=value,
            trust_class=TrustClass.TRUSTED_SYSTEM,
            source_type=SourceType.TRUSTED_SERVICE,
            source_id=service_id,
            observed_at=SystemClock().now_utc(),
        )

    @classmethod
    def from_merchant_catalog(cls, value: T, catalog_id: str) -> "Provenanced[T]":
        return cls(
            value=value,
            trust_class=TrustClass.VERIFIED_MERCHANT_DATA,
            source_type=SourceType.MERCHANT_CATALOG,
            source_id=catalog_id,
            observed_at=SystemClock().now_utc(),
        )

    @classmethod
    def from_untrusted_content(cls, value: T, origin_id: str) -> "Provenanced[T]":
        return cls(
            value=value,
            trust_class=TrustClass.UNTRUSTED_CONTENT,
            source_type=SourceType.MERCHANT_FREE_TEXT,
            source_id=origin_id,
            observed_at=SystemClock().now_utc(),
        )

    def require_authority(self) -> T:
        """Return the value only when it carries authority-level trust."""
        if self.trust_class not in _AUTHORITY_CLASSES:
            raise TrustViolation(
                f"value from {self.source_type.value} ({self.trust_class.value}) "
                f"is not authority-trusted"
            )
        return self.value

    def require_user_authority(self) -> T:
        """Return the value only when the human directly confirmed it."""
        if self.trust_class is not TrustClass.USER_AUTHORITY:
            raise TrustViolation(
                f"value from {self.source_type.value} ({self.trust_class.value}) "
                f"is not USER_AUTHORITY"
            )
        return self.value
