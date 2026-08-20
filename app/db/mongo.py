from pymongo import MongoClient
from app.core.config import get_settings

_client = None


def get_client():
    global _client

    if _client is None:
        settings = get_settings()
        _client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=10000,
        )

    return _client


def get_db():
    # Database name is taken directly from the MongoDB URI.
    # Example:
    # mongodb+srv://user:password@host/smart_learning_lab
    return get_client().get_default_database()


def ping():
    get_client().admin.command("ping")
    return True


def close():
    global _client

    if _client is not None:
        _client.close()
        _client = None
