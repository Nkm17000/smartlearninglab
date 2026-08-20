from functools import lru_cache
from pymongo import MongoClient
from app.core.config import get_settings

@lru_cache
def get_client() -> MongoClient:
    return MongoClient(
        get_settings().mongodb_uri,
        serverSelectionTimeoutMS=10000,
    )

def get_db():
    return get_client().get_default_database()

def get_database():
    return get_db()

def ping() -> bool:
    try:
        get_client().admin.command("ping")
        return True
    except Exception:
        return False

def close():
    get_client().close()

def close_mongo_connection():
    close()
