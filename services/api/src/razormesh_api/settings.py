"""Application settings (local, credential-free in Phase 1)."""

from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
