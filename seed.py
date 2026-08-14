from datetime import datetime, timezone
from pymongo import MongoClient
from app.core.config import get_settings
from app.core.security import hash_password

settings = get_settings()
client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
db = client[settings.mongodb_db]
now = datetime.now(timezone.utc)

# Categories
categories = [
    {"code": "GOVT", "name": "Government Exams", "active": True},
    {"code": "BANKING", "name": "Banking Exams", "active": True},
    {"code": "RAILWAY", "name": "Railway Exams", "active": True},
    {"code": "MBA", "name": "MBA Entrance", "active": True},
]
for doc in categories:
    db.exam_categories.update_one({"code": doc["code"]}, {"$set": {**doc, "updatedAt": now}, "$setOnInsert": {"createdAt": now}}, upsert=True)

cat_map = {x["code"]: db.exam_categories.find_one({"code": x["code"]})["_id"] for x in categories}

exams = [
    {"code": "SSC_CGL", "name": "SSC CGL", "categoryId": str(cat_map["GOVT"]), "description": "Staff Selection Commission Combined Graduate Level", "active": True},
    {"code": "SSC_CHSL", "name": "SSC CHSL", "categoryId": str(cat_map["GOVT"]), "description": "Staff Selection Commission Combined Higher Secondary Level", "active": True},
    {"code": "IBPS_PO", "name": "IBPS PO", "categoryId": str(cat_map["BANKING"]), "description": "IBPS Probationary Officer", "active": True},
    {"code": "SBI_PO", "name": "SBI PO", "categoryId": str(cat_map["BANKING"]), "description": "State Bank of India Probationary Officer", "active": True},
    {"code": "RRB_NTPC", "name": "RRB NTPC", "categoryId": str(cat_map["RAILWAY"]), "description": "Railway Recruitment Board NTPC", "active": True},
    {"code": "CAT", "name": "CAT", "categoryId": str(cat_map["MBA"]), "description": "Common Admission Test", "active": True},
]
for doc in exams:
    db.exams.update_one({"code": doc["code"]}, {"$set": {**doc, "updatedAt": now}, "$setOnInsert": {"createdAt": now}}, upsert=True)

subjects = [
    {"code": "QUANT", "name": "Quantitative Aptitude", "order": 1, "active": True},
    {"code": "REASONING", "name": "Reasoning", "order": 2, "active": True},
    {"code": "ENGLISH", "name": "English", "order": 3, "active": True},
    {"code": "GK", "name": "General Awareness", "order": 4, "active": True},
]
for doc in subjects:
    db.subjects.update_one({"code": doc["code"]}, {"$set": {**doc, "updatedAt": now}, "$setOnInsert": {"createdAt": now}}, upsert=True)

topics = [
    ("QUANT", "PERCENTAGE", "Percentage"),
    ("QUANT", "RATIO", "Ratio"),
    ("QUANT", "AVERAGE", "Average"),
    ("QUANT", "TIME_WORK", "Time & Work"),
    ("REASONING", "SYLLOGISM", "Syllogism"),
    ("REASONING", "CODING", "Coding-Decoding"),
    ("ENGLISH", "VOCABULARY", "Vocabulary"),
    ("ENGLISH", "GRAMMAR", "Grammar"),
    ("GK", "CURRENT_AFFAIRS", "Current Affairs"),
    ("GK", "POLITY", "Indian Polity"),
]
subject_ids = {x["code"]: str(db.subjects.find_one({"code": x["code"]})["_id"]) for x in subjects}
for subject_code, code, name in topics:
    db.topics.update_one(
        {"code": code},
        {"$set": {"code": code, "name": name, "subjectId": subject_ids[subject_code], "order": 1, "active": True, "updatedAt": now},
         "$setOnInsert": {"createdAt": now}},
        upsert=True,
    )

admin_email = settings.admin_email.lower()
db.users.update_one(
    {"email": admin_email},
    {"$set": {
        "name": "Smart Learning Lab Admin",
        "email": admin_email,
        "passwordHash": hash_password(settings.admin_password),
        "role": "admin",
        "status": "active",
        "updatedAt": now,
    }, "$setOnInsert": {"createdAt": now}},
    upsert=True,
)

print("Seed completed.")
print("Admin email:", admin_email)
print("Admin password: value from ADMIN_PASSWORD in .env")
client.close()
