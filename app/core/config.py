from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Learning Lab API"
    environment: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"

    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_db: str = "smart_learning_lab"

    jwt_secret_key: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    cors_origins: str = "http://localhost:8081,http://localhost:19006,http://localhost:3000"

    admin_email: str = "admin@smartlearninglab.com"
    admin_password: str = "ChangeMe123!"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
