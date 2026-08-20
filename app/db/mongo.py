from functools import lru_cache

from pymongo import MongoClient

from app.core.config import get_settings


@lru_cache
def get_client() -> MongoClient:
    settings = get_settings()

    return MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=10000,
    )


def get_db():
    """
    Return the MongoDB database defined in the URI.

    Example:
    mongodb+srv://user:password@cluster.mongodb.net/smart_learning_lab
    """
    client = get_client()
    return client.get_default_database()


def get_database():
    """Backward-compatible alias."""
    return get_db()


def ping() -> bool:
    """
    Check whether MongoDB is reachable.
    """
    try:
        get_client().admin.command("ping")
        return True
    except Exception:
        return False


def close():
    """
    Close MongoDB connection.
    """
    get_client().close()


def close_mongo_connection():
    """
    Backward-compatible alias.
    """
    close()