from bson import ObjectId
from datetime import datetime, timezone

def oid(value):
    try:
        return ObjectId(value)
    except Exception:
        return value

def serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [serialize(x) for x in value]
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items() if k != "password_hash"}
    return value

def clean_doc(doc):
    if not doc:
        return None
    return serialize(doc)

def now():
    return datetime.now(timezone.utc)
