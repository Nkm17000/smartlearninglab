from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Learning Lab API"
    environment: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # MongoDB
    #
    # Example:
    # mongodb+srv://username:password@cluster.mongodb.net/smart_learning_lab
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

    @property
    def cors_origin_list(self) -> list[str]:
        """
        Convert comma-separated CORS origins into a list.

        Example:
        CORS_ORIGINS=http://localhost:8081,http://localhost:19006

        becomes:
        [
            "http://localhost:8081",
            "http://localhost:19006"
        ]
        """
        if not self.cors_origins:
            return ["*"]

        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()