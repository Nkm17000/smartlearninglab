"""MongoDB index safety and performance helpers.

MongoDB cannot create/use a compound index that contains two array fields
because that would require parallel multikey expansion.  The taxonomy update
introduced category_ids and subcategory_ids as arrays, so any legacy compound
index containing both fields must be removed before documents can be written.
"""

from app.db.mongo import get_db
from app.core.logging_config import get_logger

logger = get_logger("smart_learning_lab.db.indexes")


TAXONOMY_COLLECTIONS = ("courses", "quizzes")


def _drop_parallel_taxonomy_indexes(collection):
    """Drop only indexes that contain both taxonomy array fields."""
    dropped = []
    for index in collection.list_indexes():
        name = index.get("name")
        keys = list((index.get("key") or {}).keys())
        if "category_ids" in keys and "subcategory_ids" in keys:
            # Never drop the _id index (it cannot match this condition anyway),
            # and only touch the known unsafe taxonomy shape.
            if name:
                collection.drop_index(name)
                dropped.append(name)
    return dropped


def ensure_safe_taxonomy_indexes():
    """Repair legacy parallel-array indexes and create safe query indexes.

    This is intentionally idempotent and runs during application startup. It
    repairs an already-deployed MongoDB database, so a manual migration is not
    required just to recover course/quiz creation after the taxonomy change.
    """
    db = get_db()

    for collection_name in TAXONOMY_COLLECTIONS:
        collection = db[collection_name]
        dropped = _drop_parallel_taxonomy_indexes(collection)
        if dropped:
            logger.warning(
                "MONGO_UNSAFE_TAXONOMY_INDEX_REMOVED | collection=%s | indexes=%s",
                collection_name,
                ",".join(dropped),
            )

        # Single-array indexes are safe. Compound indexes may contain one
        # taxonomy array plus scalar fields, but never both arrays together.
        collection.create_index("category_ids", name="category_ids_1")
        collection.create_index("subcategory_ids", name="subcategory_ids_1")
        collection.create_index("subject", name="subject_1")
        collection.create_index(
            [("is_published", 1), ("category_ids", 1), ("subject", 1)],
            name="is_published_1_category_ids_1_subject_1",
        )
        collection.create_index(
            [("is_published", 1), ("subcategory_ids", 1), ("subject", 1)],
            name="is_published_1_subcategory_ids_1_subject_1",
        )

    logger.info("MONGO_TAXONOMY_INDEXES_READY")
