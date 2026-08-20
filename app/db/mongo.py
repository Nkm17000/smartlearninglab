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
    Return the default MongoDB database from the URI.

    Example:
        mongodb+srv://user:password@cluster.mongodb.net/smart_learning_lab

    get_default_database() will return:
        smart_learning_lab
    """
    client = get_client()

    db = client.get_default_database()

    return db


def get_database():
    """
    Backward-compatible alias.
    """
    return get_db()


def close_mongo_connection():
    """
    Close the MongoDB client.
    """
    get_client().close()