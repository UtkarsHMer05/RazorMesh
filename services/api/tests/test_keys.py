"""M33 acceptance: local Ed25519 dev key generation/loading/signing."""

import stat

import pytest

from razormesh_api.keys import DevKeyError, DevSigningKeys


@pytest.fixture()
def keys(tmp_path):  # type: ignore[no-untyped-def]
    return DevSigningKeys(
        private_path=str(tmp_path / "keys" / "dev_private.pem"),
        public_path=str(tmp_path / "keys" / "dev_public.pem"),
    )


def test_generate_creates_pem_pair_with_private_permissions(keys: DevSigningKeys) -> None:
    assert not keys.both_present
    pair = keys.generate()
    assert pair.private_path.is_file() and pair.public_path.is_file()
    assert pair.private_path.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----")
    assert pair.public_path.read_bytes().startswith(b"-----BEGIN PUBLIC KEY-----")
    mode = stat.S_IMODE(pair.private_path.stat().st_mode)
    assert mode == 0o600, "private key must be owner-only"


def test_sign_and_verify_roundtrip_and_tamper_detection(keys: DevSigningKeys) -> None:
    pair = keys.ensure()
    payload = b"razormesh-ticket-payload"
    signature = pair.sign(payload)
    assert pair.verify(payload, signature)

    tampered = payload + b"x"
    assert not pair.verify(tampered, signature)


def test_load_missing_key_raises_actionable_error(keys: DevSigningKeys) -> None:
    with pytest.raises(DevKeyError, match="not found at"):
        keys.load()


def test_loaded_pair_matches_generated_material(keys: DevSigningKeys) -> None:
    generated = keys.generate()
    reloaded = keys.load()

    payload = b"same message"
    sig_from_reloaded = reloaded.sign(payload)
    assert generated.verify(payload, sig_from_reloaded)
    assert reloaded.verify(payload, generated.sign(payload))


def test_different_pairs_cannot_verify_each_other(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pair_a = DevSigningKeys(
        private_path=str(tmp_path / "a_private.pem"),
        public_path=str(tmp_path / "a_public.pem"),
    ).ensure()
    b = DevSigningKeys(
        private_path=str(tmp_path / "b_private.pem"),
        public_path=str(tmp_path / "b_public.pem"),
    ).ensure()

    payload = b"cross-key"
    assert b.verify(payload, pair_a.sign(payload)) is False


def test_ensure_is_idempotent(keys: DevSigningKeys) -> None:
    first = keys.ensure()
    second = keys.ensure()
    assert first.private_path == second.private_path
    # same underlying key material
    payload = b"idempotent"
    assert second.verify(payload, first.sign(payload))
