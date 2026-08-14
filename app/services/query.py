from math import ceil
from app.utils import serialize_doc


def paginated(collection, query, page=1, limit=20, sort=None, projection=None):
    page = max(1, page)
    limit = min(max(1, limit), 100)
    total = collection.count_documents(query)
    cursor = collection.find(query, projection)
    if sort:
        cursor = cursor.sort(sort)
    cursor = cursor.skip((page - 1) * limit).limit(limit)
    items = [serialize_doc(x) for x in cursor]
    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": ceil(total / limit) if total else 0,
    }
