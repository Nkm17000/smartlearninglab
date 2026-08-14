from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import get_settings

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
    return _client


def get_db() -> Database:
    return get_client()[get_settings().mongodb_db]


def ping() -> bool:
    get_client().admin.command("ping")
    return True


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
