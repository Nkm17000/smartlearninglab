from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    mongodb_url: str
    mongodb_database: str = "smartlearninglab"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    cors_origins: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def mongodb_uri(self):
        return self.mongodb_url

    @property
    def jwt_secret(self):
        return self.jwt_secret_key


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()