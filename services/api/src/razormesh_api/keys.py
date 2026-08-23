"""M33: local Ed25519 dev signing keys (Phase-1 only; never real credentials).

Keys live under ``infra/keys/`` (gitignored). Private keys are written with
default permissions and NEVER leave the machine. Missing keys raise a clear,
actionable error instead of silently generating new authority mid-run.
"""

from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


class DevKeyError(Exception):
    """Raised when dev signing keys are missing or unusable."""


@dataclass(frozen=True)
class DevKeyPair:
    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey
    private_path: Path
    public_path: Path

    def sign(self, payload: bytes) -> bytes:
        return self.private_key.sign(payload)

    def verify(self, payload: bytes, signature: bytes) -> bool:
        try:
            self.public_key.verify(signature, payload)
            return True
        except InvalidSignature:
            return False


def _read_private(path: Path) -> object:
    if not path.is_file():
        raise DevKeyError(
            f"dev signing key not found at {path}. "
            "Generate it once with: python -m razormesh_api.keys "
            "(keys are local-only and gitignored)"
        )
    try:
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    except Exception as exc:
        raise DevKeyError(f"unreadable dev private key at {path}: {exc}") from exc


def _read_public(path: Path) -> object:
    if not path.is_file():
        raise DevKeyError(
            f"dev public key not found at {path}. "
            "Regenerate the pair with: python -m razormesh_api.keys"
        )
    try:
        return serialization.load_pem_public_key(path.read_bytes())
    except Exception as exc:
        raise DevKeyError(f"unreadable dev public key at {path}: {exc}") from exc


def _as_ed25519_private(key: object) -> Ed25519PrivateKey:
    if not isinstance(key, Ed25519PrivateKey):
        raise DevKeyError("private key exists but is not Ed25519")
    return key


def _as_ed25519_public(key: object) -> Ed25519PublicKey:
    if not isinstance(key, Ed25519PublicKey):
        raise DevKeyError("public key exists but is not Ed25519")
    return key


def _load_pair(private_path: Path, public_path: Path) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    return (
        _as_ed25519_private(_read_private(private_path)),
        _as_ed25519_public(_read_public(public_path)),
    )


class DevSigningKeys:
    """Loads-or-generates a local Ed25519 pair at fixed paths."""

    def __init__(self, private_path: str, public_path: str) -> None:
        self._private_path = Path(private_path)
        self._public_path = Path(public_path)

    @property
    def both_present(self) -> bool:
        return self._private_path.is_file() and self._public_path.is_file()

    def load(self) -> DevKeyPair:
        private_key, public_key = _load_pair(self._private_path, self._public_path)
        return DevKeyPair(
            private_key=private_key,
            public_key=public_key,
            private_path=self._private_path,
            public_path=self._public_path,
        )

    def generate(self) -> DevKeyPair:
        private = Ed25519PrivateKey.generate()
        private_pem = private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        )
        public_pem = private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        )
        self._private_path.parent.mkdir(parents=True, exist_ok=True)
        self._public_path.parent.mkdir(parents=True, exist_ok=True)
        # 0o600 on the private material; public half is world-readable by design.
        self._private_path.write_bytes(private_pem)
        self._private_path.chmod(0o600)
        self._public_path.write_bytes(public_pem)
        return self.load()

    def ensure(self) -> DevKeyPair:
        """Load the existing pair, generating only when absent."""
        if self.both_present:
            return self.load()
        return self.generate()


def default_from_settings():  # type: ignore[no-untyped-def]
    from razormesh_api.settings import get_settings

    s = get_settings()
    return DevSigningKeys(
        private_path=s.dev_ticket_private_key_path,
        public_path=s.dev_ticket_public_key_path,
    )


if __name__ == "__main__":
    keys = default_from_settings().ensure()
    print(f"dev signing keys ready:\n  private: {keys.private_path}\n  public:  {keys.public_path}")
