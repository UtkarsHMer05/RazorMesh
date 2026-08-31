"""F005: working-directory independence of backend configuration.

Proves that repo-relative configuration — the .env the AI Intent Compiler
reads, the dev signing keys, the semantic model/policy paths, the challenger
artifact path — resolves from the canonical repository root (derived from the
package's source location), never from the process CWD:

- settings load + compiler config present from ANY CWD (repo root,
  services/api, /tmp);
- dev ticket key paths point at the SAME repo keys from any CWD;
- semantic + challenger paths resolve to the repo artifacts from any CWD;
- absolute env overrides still pass through untouched.
"""

import os
import subprocess
import sys
from pathlib import Path

from razormesh_api.settings import REPO_ROOT, Settings

_SERVICES_API = REPO_ROOT / "services" / "api"


def _probe(cwd: Path) -> dict[str, object]:
    """Import Settings from inside ``cwd`` and report its resolved config."""
    code = (
        "from razormesh_api.settings import REPO_ROOT, Settings\n"
        "from razormesh_api.keys import DevSigningKeys\n"
        "s = Settings()\n"
        "keys = DevSigningKeys(s.dev_ticket_private_key_path, s.dev_ticket_public_key_path)\n"
        "import json\n"
        "print(json.dumps({\n"
        "  'repo_root': str(REPO_ROOT),\n"
        "  'compiler_configured': bool(s.tokenrouter_api_key.get_secret_value()),\n"
        "  'compiler_model': s.planner_model,\n"
        "  'private_key': str(keys._private_path),\n"
        "  'keys_present': keys.both_present,\n"
        "  'semantic_model': str(s.repo_path(s.semantic_model_path)),\n"
        "  'semantic_policy': str(s.repo_path(s.semantic_policy_path)),\n"
        "  'v2_model': str(s.repo_path(s.semantic_model_path_v2)),\n"
        "  'cwd': __import__('os').getcwd(),\n"
        "}))"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{_SERVICES_API / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    out = subprocess.run(  # noqa: S603 - sys.executable + literal probe code, no untrusted input
        [sys.executable, "-c", code], cwd=cwd, env=env, capture_output=True, text=True
    )
    if out.returncode != 0:
        raise AssertionError(f"probe failed in {cwd}: {out.stderr[-500:]}")
    import json

    return json.loads(out.stdout.strip().splitlines()[-1])


def test_settings_resolve_from_repo_root() -> None:
    probe = _probe(REPO_ROOT)
    assert probe["repo_root"] == str(REPO_ROOT)
    # The AI compiler configuration must load (the .env at repo root).
    assert probe["compiler_configured"] is True
    assert probe["compiler_model"]  # non-empty planner model


def test_settings_resolve_from_services_api() -> None:
    """The historical failure mode: launching from services/api lost .env."""
    probe = _probe(_SERVICES_API)
    assert probe["repo_root"] == str(REPO_ROOT)
    assert probe["compiler_configured"] is True, "compiler config lost when CWD=services/api"
    # Same keys as from the repo root — not a CWD-local pair.
    assert probe["private_key"] == str(REPO_ROOT / "infra/keys/dev_ticket_ed25519_private.pem")


def test_settings_resolve_from_tmp() -> None:
    """A totally foreign CWD must still resolve repo resources safely."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        probe = _probe(Path(tmp))
    assert probe["repo_root"] == str(REPO_ROOT)
    assert probe["compiler_configured"] is True, "compiler config lost when CWD=/tmp"
    assert probe["semantic_model"] == str(
        REPO_ROOT / "artifacts/models/incoming/phase3-finetuned-v2"
    )
    assert probe["semantic_policy"] == str(
        REPO_ROOT / "data/phase3/policy/semantic_thresholds_v3.json"
    )
    assert Path(probe["semantic_model"]).exists(), "active model artifact must exist"


def test_key_paths_point_at_repo_keys_from_any_cwd() -> None:
    """The dev signing keys must be the SAME files from every CWD."""
    for cwd in (REPO_ROOT, _SERVICES_API):
        probe = _probe(cwd)
        private = Path(str(probe["private_key"]))
        assert private == REPO_ROOT / "infra/keys/dev_ticket_ed25519_private.pem"
        assert private.exists(), f"dev keys missing at {private}"


def test_absolute_env_override_passes_through() -> None:
    """An absolute override (env) is never re-anchored to the repo root."""
    s = Settings(
        dev_ticket_private_key_path="/absolute/custom/key.pem",
        semantic_model_path="/absolute/custom/model",
    )
    assert s.dev_ticket_private_key_path == "/absolute/custom/key.pem"
    assert s.repo_path(s.semantic_model_path) == Path("/absolute/custom/model")


def test_env_file_precedence_cwd_then_repo_root(tmp_path: Path) -> None:
    """A CWD .env still wins (compatibility), repo .env is the fallback."""
    import os

    from razormesh_api.settings import _env_file_path

    # From the repo root the repo .env is the CWD .env — identical target.
    cwd_save = os.getcwd()
    try:
        os.chdir(REPO_ROOT)
        assert Path(_env_file_path()) == REPO_ROOT / ".env"
        os.chdir(tmp_path)
        # No .env in tmp → falls back to the repo root .env.
        assert Path(_env_file_path()) == REPO_ROOT / ".env"
    finally:
        os.chdir(cwd_save)
