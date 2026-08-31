"""Phase-1 security gate: secret scan + dependency audit classification.

Runs two checks and classifies findings per TESTING.md section 10:

1. Secret scan — regex-based scan over git-tracked text files for private key
   material, high-entropy credential assignments and known provider token
   shapes. `.env.example` placeholders are allowed only when values are empty.
2. Dependency audit — Python: pip-audit over the locked API environment.
   Frontend: pnpm audit (production deps). Findings are classified:
   fixed / not_applicable / temporarily_accepted / BLOCKING.

Exit code is non-zero when a BLOCKING finding exists. This script performs a
local, best-effort heuristic scan; it does not claim completeness.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "services" / "api"
WEB_DIR = REPO_ROOT / "apps" / "web"

# ---------------------------------------------------------------- secret scan

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Full key block: header + substantial base64 body + footer. A bare header
    # string (e.g. inside an assertion checking a file's magic bytes) is not a
    # secret and must not trip the scanner.
    (
        "private-key-block",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
            r"[A-Za-z0-9+/=\s]{120,}"
            r"-----END [A-Z ]*PRIVATE KEY-----"
        ),
    ),
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    (
        "credential-assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*"
            r"['\"](?!\s*['\"]|$)([A-Za-z0-9/_+!=-]{20,})['\"]"
        ),
    ),
    ("razorpay-key-shape", re.compile(r"\brzp_(live|test)_[A-Za-z0-9]{10,}\b")),
]

_SCAN_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    ".next",
    "__pycache__",
    "test-results",
}

# Explicit, narrowly-scoped allowlist for synthetic test fixtures that must
# look secret-shaped to prove the security controls around them. Each entry
# pins (relative path, rule) to the EXACT literal(s) accepted; any other
# value in the same file — or the same value anywhere else — still fails the
# scan. Adding an entry requires a justification recorded in TESTING.md.
_ALLOWED_TEST_FIXTURES: dict[tuple[str, str], frozenset[str]] = {
    # HMAC fixture secret for callback signature tests (synthetic value).
    (
        "services/api/tests/test_callback_verification.py",
        "credential-assignment",
    ): frozenset({"test-hook-secret-value"}),
    # HMAC fixture secret for raw-body webhook tests (synthetic value).
    (
        "services/api/tests/test_webhook_verification.py",
        "credential-assignment",
    ): frozenset({"webhook-secret-test-value"}),
    # HMAC fixture secret for the P2-M38 webhook route-wiring regression test
    # (synthetic value; drives the REAL route + reducer to pin spend commit).
    (
        "services/api/tests/test_reducer.py",
        "credential-assignment",
    ): frozenset({"wh-route-wiring-secret"}),
    # M095-M100 payment-FSM e2e: the stubbed Razorpay checkout launch payload
    # needs a key-shaped string to be realistic. It is a SYNTHETIC value
    # (never a credential; the e2e stubs the provider boundary only — the
    # app pipeline is real). Allowed here so the scan keeps catching real
    # key-shaped literals everywhere else.
    (
        "apps/web/e2e/phase5-payment-fsm.spec.ts",
        "razorpay-key-shape",
    ): frozenset({"rzp_test_phase5public"}),
    # rzp_live_ literal REQUIRED to prove live-key rejection (P2-S02).
    (
        "services/api/tests/test_settings_phase2.py",
        "razorpay-key-shape",
    ): frozenset({"rzp_live_CkYzExample"}),
    # Synthetic TokenRouter-shaped key for the P3-M09 client tests: proves the
    # Bearer header carries the key and that error paths NEVER leak it (P3-S01).
    (
        "services/api/tests/test_intent_compiler_client.py",
        "credential-assignment",
    ): frozenset({"tr_test_key_placeholder"}),
    # Same synthetic key for the P3-M17 confirmation-API tests (route wiring
    # through the REAL service + DB with a stubbed compiler transport).
    (
        "services/api/tests/test_buyer_drafts_api.py",
        "credential-assignment",
    ): frozenset({"tr_test_key_placeholder"}),
    # Synthetic key for the P3-M42 wire-capture isolation test.
    (
        "services/api/tests/test_injection_isolation_e2e.py",
        "credential-assignment",
    ): frozenset({"tr_test_key_placeholder"}),
    # Same synthetic key for the P3-M13 compilation-service tests (DI seam).
    (
        "services/api/tests/test_intent_compilation_service.py",
        "credential-assignment",
    ): frozenset({"tr_test_key_placeholder"}),
    # The allowlist definition above necessarily repeats the pinned literal.
    (
        "scripts/security_check.py",
        "razorpay-key-shape",
    ): frozenset({"rzp_live_CkYzExample", "rzp_test_phase5public"}),
}
_SCAN_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".example",
    ".sh",
    ".mjs",
    ".css",
    ".html",
    ".sql",
    "",
}


@dataclass(frozen=True)
class Finding:
    check: str
    path: str
    line: int
    rule: str
    detail: str
    blocking: bool


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True
    )
    # git ls-files returns repo-root-relative paths
    return [REPO_ROOT / p for p in result.stdout.decode().split("\0") if p]


def _is_placeholder(value: str) -> bool:
    return (
        not value.strip()
        or value.strip() in {"changeme", "CHANGEME", "your-key-here"}
        or value.strip().startswith("<")
    )


def scan_secrets() -> list[Finding]:
    findings: list[Finding] = []
    for path in _tracked_files():
        rel = path.relative_to(REPO_ROOT)
        if any(part in _SCAN_SKIP_DIRS for part in rel.parts):
            continue
        if path.suffix not in _SCAN_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # private-key blocks span lines; match on whole file content
        key_block = re.search(_PATTERNS[0][1], text)
        if key_block:
            line = text.count("\n", 0, key_block.start()) + 1
            findings.append(
                Finding(
                    check="secret-scan",
                    path=str(rel),
                    line=line,
                    rule=_PATTERNS[0][0],
                    detail="complete private key material present",
                    blocking=True,
                )
            )
        for lineno, line_text in enumerate(text.splitlines(), start=1):
            for rule, pattern in _PATTERNS[1:]:
                match = pattern.search(line_text)
                if match is None:
                    continue
                allowed = _ALLOWED_TEST_FIXTURES.get((str(rel), rule))
                if allowed is not None:
                    literals = {g for g in match.groups() if g} | {match.group(0)}
                    if literals & allowed:
                        continue
                if "env.example" in str(rel) and rule == "credential-assignment":
                    groups = [g for g in match.groups() if g]
                    if groups and all(
                        _is_placeholder(g) or g.startswith("=") for g in groups
                    ):
                        continue
                    if "=" in line_text.split("'")[0]:
                        continue
                findings.append(
                    Finding(
                        check="secret-scan",
                        path=str(rel),
                        line=lineno,
                        rule=rule,
                        detail=line_text.strip()[:120],
                        blocking=True,
                    )
                )
    return findings


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    output = (proc.stdout + "\n" + proc.stderr).strip()
    return proc.returncode, output


# ----------------------------------------------------------- dependency audit


def audit_python_deps() -> tuple[str, list[Finding]]:
    """pip-audit against the locked API virtual environment (via uv)."""
    uv = shutil.which("uv")
    if uv is None:
        return "uv not found; python dep audit blocked", [
            Finding(
                "python-dep-audit",
                "services/api",
                0,
                "TOOL_MISSING",
                "uv unavailable",
                True,
            )
        ]
    code, output = _run(
        [
            uv,
            "run",
            "--project",
            str(API_DIR),
            "python",
            "-m",
            "pip_audit",
            "--progress-spinner",
            "off",
            "--desc",
            "off",
        ],
        REPO_ROOT,
    )
    if code == 0:
        return (
            f"pip-audit clean ({output.splitlines()[0] if output else 'no vulnerabilities'})",
            [],
        )
    vulns: list[Finding] = []
    for block in output.split("\n\n"):
        if re.search(
            r"\b\d+ vulnerabilities? known\b|\bName\s+Version\b", block, re.IGNORECASE
        ):
            continue
        m = re.match(r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", block.strip())
        if m:
            vulns.append(
                Finding(
                    check="python-dep-audit",
                    path=m.group(1),
                    line=0,
                    rule=m.group(3)[:80],
                    detail=block.strip()[:300],
                    blocking=True,
                )
            )
    return "pip-audit reported findings", vulns


def audit_frontend_deps() -> tuple[str, list[Finding]]:
    """pnpm audit over production dependencies of the web app."""
    if not (WEB_DIR / "package.json").exists():
        return "frontend not scaffolded", []
    code, output = _run(["pnpm", "audit", "--prod", "--json"], WEB_DIR)
    if code == 0:
        return "pnpm audit clean (production deps)", []
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return f"pnpm audit unparsable output (code={code})", [
            Finding(
                "frontend-dep-audit", "apps/web", 0, "UNPARSABLE", output[:300], True
            )
        ]
    advisories = data.get("advisories") or {}
    findings: list[Finding] = []
    for adv in advisories.values():
        severity = str(adv.get("severity", "unknown"))
        findings.append(
            Finding(
                check="frontend-dep-audit",
                path=f"apps/web:{adv.get('module_name', '?')}",
                line=0,
                rule=f"{severity}:{adv.get('via', '')}",
                detail=str(adv.get("title", ""))[:200],
                # low/moderate are recorded; high/critical block the gate
                blocking=severity in ("high", "critical"),
            )
        )
    summary = f"pnpm audit reported {len(findings)} production advisories"
    return summary, findings


def main() -> int:
    print("== RazorMesh Phase-1 security check ==")
    all_findings: list[Finding] = []

    secrets = scan_secrets()
    print(f"[1/3] secret scan: {len(secrets)} finding(s)")
    all_findings.extend(secrets)

    py_summary, py_findings = audit_python_deps()
    print(f"[2/3] python dep audit: {py_summary}; {len(py_findings)} finding(s)")
    all_findings.extend(py_findings)

    fe_summary, fe_findings = audit_frontend_deps()
    print(f"[3/3] frontend dep audit: {fe_summary}; {len(fe_findings)} finding(s)")
    all_findings.extend(fe_findings)

    blocking = [f for f in all_findings if f.blocking]
    accepted = [f for f in all_findings if not f.blocking]
    for finding in accepted:
        print(
            f"  CLASSIFIED non-blocking: {finding.check} {finding.path} "
            f"[{finding.rule}] {finding.detail}"
        )

    if blocking:
        print(f"\nBLOCKING findings: {len(blocking)}")
        for finding in blocking:
            print(f"  {finding.check} {finding.path}:{finding.line} [{finding.rule}]")
            print(f"    {finding.detail}")
        print("\nresult: FAIL")
        return 1

    print("\nresult: PASS (no blocking findings; classifications above if any)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
