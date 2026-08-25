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
        _client = MongoClient(
            s.mongodb_uri,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=5000,
            socketTimeoutMS=15000,
            maxPoolSize=50,
            minPoolSize=5,
            retryWrites=True,
        )
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



def repair_taxonomy_indexes():
    """Repair unsafe MongoDB indexes introduced by the category/subcategory migration.

    MongoDB cannot create a multikey compound index containing two array fields.
    Older migrations attempted to index category_ids + subcategory_ids together,
    which causes every course/quiz write to fail with error 171.
    """
    db = get_db()
    unsafe = []
    for collection_name in ("courses", "quizzes", "topics"):
        collection = db[collection_name]
        try:
            indexes = list(collection.list_indexes())
        except Exception:
            continue
        for index in indexes:
            keys = list((index.get("key") or {}).keys())
            if "category_ids" in keys and "subcategory_ids" in keys:
                name = index.get("name")
                if name and name != "_id_":
                    try:
                        collection.drop_index(name)
                        unsafe.append(f"{collection_name}.{name}")
                        logger.warning("MONGODB_UNSAFE_TAXONOMY_INDEX_REMOVED | collection=%s | index=%s", collection_name, name)
                    except Exception:
                        logger.exception("MONGODB_TAXONOMY_INDEX_REPAIR_FAILED | collection=%s | index=%s", collection_name, name)

    # Safe indexes contain at most one array field. Reuse an existing index
    # with the same key pattern instead of creating duplicate indexes under a
    # second name.
    def ensure_index(collection, keys, name):
        wanted = list(keys)
        existing = {tuple((idx.get('key') or {}).items()) for idx in collection.list_indexes()}
        if tuple(wanted) not in existing:
            collection.create_index(wanted, name=name)

    ensure_index(db.courses, [('is_published', 1), ('category_ids', 1), ('subject', 1)], 'course_publish_category_subject_idx')
    ensure_index(db.courses, [('is_published', 1), ('subcategory_ids', 1), ('subject', 1)], 'course_publish_subcategory_subject_idx')
    ensure_index(db.quizzes, [('is_published', 1), ('category_ids', 1), ('subject', 1)], 'quiz_publish_category_subject_idx')
    ensure_index(db.quizzes, [('is_published', 1), ('subcategory_ids', 1), ('subject', 1)], 'quiz_publish_subcategory_subject_idx')
    ensure_index(db.topics, [('course_id', 1), ('is_published', 1), ('category_ids', 1)], 'topic_course_publish_category_idx')
    ensure_index(db.topics, [('course_id', 1), ('is_published', 1), ('subcategory_ids', 1)], 'topic_course_publish_subcategory_idx')
    return unsafe

def close():
    global _client
    if _client is not None:
        logger.info("MONGODB_CLIENT_CLOSE")
        _client.close()
        _client = None
