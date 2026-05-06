"""Load settings from the environment."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Hackathon WhatsApp API", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    port: int = Field(default=8080, alias="PORT")

    kapso_api_key: str = Field(default="", alias="KAPSO_API_KEY")
    kapso_phone_number_id: str = Field(default="", alias="KAPSO_PHONE_NUMBER_ID")
    kapso_api_url: str = Field(default="https://api.kapso.ai", alias="KAPSO_API_URL")
    kapso_verify_token: str = Field(default="", alias="KAPSO_VERIFY_TOKEN")
    kapso_webhook_secret: str = Field(default="", alias="KAPSO_WEBHOOK_SECRET")
    kapso_flow_id: str = Field(default="", alias="KAPSO_FLOW_ID")

    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_currency: str = Field(default="usd", alias="STRIPE_CURRENCY")

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_fallback_model: str = Field(default="gemini/gemini-2.5-flash", alias="GEMINI_FALLBACK_MODEL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
