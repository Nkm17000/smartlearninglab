from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Learning Lab API"
    environment: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # MongoDB
    #
    # IMPORTANT:
    # Put the database name directly in the URI:
    #
    # mongodb+srv://USER:PASSWORD@HOST/smart_learning_lab
    #
    # This prevents the application from accidentally selecting
    # a wrongly named database.
    mongodb_uri: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # CORS
    cors_origins: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()