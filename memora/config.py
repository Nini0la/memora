from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMORA_", extra="ignore")

    app_env: str = "dev"
    database_url: str = "sqlite:///./memora.db"
    long_note_warning_chars: int = 12000
    password_min_length: int = 8
    password_pepper: str = "memora-local-pepper"
