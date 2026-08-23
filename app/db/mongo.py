from pymongo import MongoClient
from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger("smart_learning_lab.db.mongo")
_client = None


def get_client():
    global _client
    if _client is None:
        s = get_settings()
        # Never print the MongoDB URI because it may contain credentials.
        logger.info("MONGODB_CLIENT_CREATE | serverSelectionTimeoutMS=10000")
        _client = MongoClient(s.mongodb_uri, serverSelectionTimeoutMS=10000)
    return _client


def get_db():
    # Database name is intentionally taken from the URI.
    # Example: ...mongodb.net/smart_learning_lab
    db = get_client().get_default_database()
    logger.debug("MONGODB_DATABASE_READY | name=%s", db.name)
    return db


def ping():
    logger.debug("MONGODB_PING_START")
    get_client().admin.command("ping")
    logger.debug("MONGODB_PING_OK")
    return True


def close():
    global _client
    if _client is not None:
        logger.info("MONGODB_CLIENT_CLOSE")
        _client.close()
        _client = None
