"""Typed application settings (local-first; Razorpay Test Mode in Phase 2)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://razormesh:razormesh_local_dev@127.0.0.1:15432/razormesh"
    )
    redis_url: str = "redis://127.0.0.1:16379/0"
    web_origin: str = "http://localhost:3000"
    policy_version: str = "phase1-policy-v1"
    mock_payment_provider: bool = True
    dev_ticket_private_key_path: str = "./infra/keys/dev_ticket_ed25519_private.pem"
    dev_ticket_public_key_path: str = "./infra/keys/dev_ticket_ed25519_public.pem"

    # ------------------------------------------------------------------
    # Payment provider selection (Phase 2)
    # ------------------------------------------------------------------
    # Canonical selector; mock stays available for CI/fault injection (P2-S20).
    payment_provider: Literal["mock", "razorpay"] = "mock"

    # Razorpay Test Mode configuration. Secrets are SecretStr so accidental
    # repr/logging of the settings object never leaks them (P2-S03/S04).
    razorpay_mode: Literal["test"] = "test"
    razorpay_key_id: str = ""
    razorpay_key_secret: SecretStr = SecretStr("")
    razorpay_webhook_secret: SecretStr = SecretStr("")
    razorpay_api_base_url: str = "https://api.razorpay.com/v1"
    razorpay_request_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    razorpay_webhook_path: str = "/api/v1/webhooks/razorpay"
    razorpay_webhook_public_url: str = ""

    # P3-M09 (D-038): Intent Compiler provider via TokenRouter. Backend-only
    # secrets (P3-S01); base URL default is the DOCUMENTED endpoint (R-019) —
    # .env may override; M10 probe is the authority on what actually works.
    tokenrouter_api_key: SecretStr = SecretStr("")
    tokenrouter_base_url: str = "https://api.tokenrouter.io/v1"
    planner_model: str = "qwen/qwen3.8-max-free"
    tokenrouter_timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    # ------------------------------------------------------------------
    # Semantic verifier runtime (P3-M40 corrected; correction brief §14)
    # ------------------------------------------------------------------
    # Production/default backend is the fine-tuned DeBERTa NLI verifier.
    # "deterministic_test_stub" is an EXPLICIT test/fallback selection and is
    # never silently substituted while the app reports a DeBERTa runtime.
    # "deberta_v2" is the AgentPay-IR v2 candidate backend (master prompt
    # §16A scaffolding): it runs the artifact at semantic_model_path_v2 and
    # fails CLOSED when that artifact is absent — never a keyword fallback.
    semantic_verifier_backend: Literal[
        "deberta", "deberta_v2", "deterministic_test_stub"
    ] = "deberta"
    semantic_model_path: str = "artifacts/models/incoming/phase3-finetuned-v2"
    semantic_model_path_v2: str = "artifacts/models/incoming/agentpay-ir-v2-finetuned"
    semantic_policy_path: str = "data/phase3/policy/semantic_thresholds_v3.json"

    @property
    def tokenrouter_credentials_present(self) -> bool:
        return bool(self.tokenrouter_api_key.get_secret_value())

    @property
    def razorpay_credentials_present(self) -> bool:
        return bool(self.razorpay_key_id) and bool(self.razorpay_key_secret.get_secret_value())


class ProviderConfigError(Exception):
    """Raised when the selected provider configuration is unsafe/incomplete.

    Messages name the offending ENV VARIABLE only — never any value.
    """

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


def validate_payment_provider_config(settings: Settings) -> None:
    """Fail-safe guard for real-provider use (P2-S01..S03, P2-S20, P2-S21).

    - Live key prefixes are rejected outright, in ANY provider mode.
    - Real-provider execution requires RAZORPAY_MODE=test and all three
      credentials; missing entries are reported by variable NAME.
    - Mock mode requires no Razorpay credentials at all.
    """
    problems: list[str] = []

    if settings.razorpay_key_id.startswith("rzp_live_"):
        problems.append(
            "RAZORPAY_LIVE_KEY_REJECTED: RAZORPAY_KEY_ID has a live-mode prefix; "
            "RazorMesh Phase 2 permits TEST MODE only"
        )

    if settings.payment_provider == "razorpay":
        if not settings.razorpay_key_id:
            problems.append("RAZORPAY_KEY_ID is required when PAYMENT_PROVIDER=razorpay")
        elif not settings.razorpay_key_id.startswith("rzp_test_"):
            problems.append(
                "RAZORPAY_TEST_MODE_REQUIRED: RAZORPAY_KEY_ID must use the test-mode prefix"
            )
        if not settings.razorpay_key_secret.get_secret_value():
            problems.append("RAZORPAY_KEY_SECRET is required when PAYMENT_PROVIDER=razorpay")
        if not settings.razorpay_webhook_secret.get_secret_value():
            problems.append("RAZORPAY_WEBHOOK_SECRET is required when PAYMENT_PROVIDER=razorpay")
        if settings.razorpay_api_base_url.rstrip("/") != "https://api.razorpay.com/v1":
            problems.append(
                "RAZORPAY_TEST_MODE_REQUIRED: RAZORPAY_API_BASE_URL must use the official "
                "HTTPS API endpoint"
            )

    if problems:
        raise ProviderConfigError(problems)


@lru_cache
def get_settings() -> Settings:
    return Settings()
