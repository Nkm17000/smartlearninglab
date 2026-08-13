from bson import ObjectId

def object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise ValueError("Invalid ObjectId")
    return ObjectId(value)

def serialize_document(document):
    if not document:
        return None
    result = dict(document)
    if "_id" in result:
        result["id"] = str(result.pop("_id"))
    for key, value in list(result.items()):
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, list):
            result[key] = [str(v) if isinstance(v, ObjectId) else v for v in value]
    return result
