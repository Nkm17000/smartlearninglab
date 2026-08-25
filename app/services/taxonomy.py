from datetime import datetime, timezone
import re
from fastapi import HTTPException
from app.db.mongo import get_db

DEFAULT_TAXONOMY = {
    "SSC": ["SSC CGL", "SSC CHSL", "SSC CPO", "SSC MTS", "SSC GD"],
    "Railway": ["RRB NTPC", "RRB Group D", "RRB ALP", "RRB JE"],
    "Banking": ["IBPS PO", "IBPS Clerk", "SBI PO", "SBI Clerk", "RBI Grade B", "RBI Assistant"],
    "UPSC": ["UPSC Civil Services", "UPSC CDS", "UPSC NDA"],
    "Teaching": ["CTET", "TET", "KVS", "DSSSB", "REET"],
    "Defence": ["NDA", "CDS", "AFCAT", "Agniveer"],
    "State Exams": ["State PSC", "State SSC", "State Police", "State Teacher Exams"],
    "General": ["General Competitive Exams", "General Knowledge"],
    "English Spoken": ["Spoken English", "Business English", "Interview English"],
    "Computer": ["Computer Fundamentals", "Programming", "Web Development", "Database", "Software Development"],
    "Other": ["Other Exams", "Other Learning"]
}


def now():
    return datetime.now(timezone.utc)


def clean(v):
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [clean(x) for x in v]
    if hasattr(v, "isoformat"):
        return v.isoformat()
    try:
        from bson import ObjectId
        if isinstance(v, ObjectId):
            return str(v)
    except Exception:
        pass
    return v


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")


def ensure_seed():
    db = get_db()
    categories = db.categories
    subcategories = db.subcategories
    for name, children in DEFAULT_TAXONOMY.items():
        category = categories.find_one({"slug": slug(name)})
        if not category:
            category = {
                "_id": slug(name),
                "name": name,
                "slug": slug(name),
                "is_active": True,
                "created_at": now(),
                "updated_at": now(),
            }
            categories.insert_one(category)
        for child in children:
            if not subcategories.find_one({"category_id": category["_id"], "slug": slug(child)}):
                subcategories.insert_one({
                    "_id": f"{category['_id']}:{slug(child)}",
                    "category_id": category["_id"],
                    "name": child,
                    "slug": slug(child),
                    "is_active": True,
                    "created_at": now(),
                    "updated_at": now(),
                })
    categories.create_index("slug", unique=True)
    subcategories.create_index([("category_id", 1), ("slug", 1)], unique=True)
    subcategories.create_index("category_id")
    return db


def all_taxonomy():
    db = ensure_seed()
    cats = list(db.categories.find({"is_active": {"$ne": False}}).sort("name", 1))
    result = []
    for c in cats:
        subs = list(db.subcategories.find({"category_id": c["_id"], "is_active": {"$ne": False}}).sort("name", 1))
        result.append({"id": str(c["_id"]), "name": c["name"], "slug": c.get("slug"), "subcategories": [
            {"id": str(s["_id"]), "name": s["name"], "slug": s.get("slug"), "category_id": str(c["_id"])} for s in subs
        ]})
    return result


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in str(value).split(",") if x.strip()]


def resolve_links(category_ids=None, categories=None, subcategory_ids=None, subcategories=None):
    db = ensure_seed()
    cat_values = _as_list(category_ids) + _as_list(categories)
    sub_values = _as_list(subcategory_ids) + _as_list(subcategories)

    cat_ids = []
    for value in cat_values:
        doc = db.categories.find_one({"_id": value}) or db.categories.find_one({"name": {"$regex": f"^{re.escape(value)}$", "$options": "i"}})
        if not doc:
            raise HTTPException(422, f"Unknown category '{value}'. Create it in Admin → Taxonomy first.")
        if str(doc["_id"]) not in cat_ids:
            cat_ids.append(str(doc["_id"]))

    sub_ids = []
    for value in sub_values:
        doc = db.subcategories.find_one({"_id": value}) or db.subcategories.find_one({"name": {"$regex": f"^{re.escape(value)}$", "$options": "i"}})
        if not doc:
            raise HTTPException(422, f"Unknown subcategory '{value}'. Create it under its category first.")
        sid = str(doc["_id"])
        if sid not in sub_ids:
            sub_ids.append(sid)
        cid = str(doc["category_id"])
        if cid not in cat_ids:
            raise HTTPException(422, f"Subcategory '{doc['name']}' belongs to category '{cid}', which is not selected.")

    if not cat_ids:
        raise HTTPException(422, "At least one category is required.")
    if not sub_ids:
        raise HTTPException(422, "At least one subcategory is required.")

    cats = list(db.categories.find({"_id": {"$in": cat_ids}}))
    subs = list(db.subcategories.find({"_id": {"$in": sub_ids}}))
    return {
        "category_ids": cat_ids,
        "categories": [x["name"] for x in sorted(cats, key=lambda x: x["name"].casefold())],
        "subcategory_ids": sub_ids,
        "subcategories": [x["name"] for x in sorted(subs, key=lambda x: x["name"].casefold())],
    }

SUBJECT_DEFAULT_CATEGORIES = {
    "English": ["SSC", "Railway", "Banking", "UPSC", "Teaching", "Defence", "State Exams", "General", "English Spoken", "Other"],
    "Hindi": ["SSC", "Railway", "Banking", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
    "Math": ["SSC", "Railway", "Banking", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
    "Reasoning": ["SSC", "Railway", "Banking", "UPSC", "Teaching", "Defence", "State Exams", "General", "Other"],
    "Java": ["Computer"], "Python": ["Computer"], "PHP": ["Computer"], "SQL": ["Computer"],
    "DBMS": ["Computer"], "Computer": ["Computer"], "Operating Systems": ["Computer"],
    "Networking": ["Computer"], "Web Development": ["Computer"], "Spring Boot": ["Computer"],
    "Microservices": ["Computer"]
}


def default_links_for_subject(subject):
    db = ensure_seed()
    names = SUBJECT_DEFAULT_CATEGORIES.get(str(subject).strip(), ["Other"])
    cat_docs = [db.categories.find_one({"name": n}) for n in names]
    cat_docs = [x for x in cat_docs if x]
    cat_ids = [str(x["_id"]) for x in cat_docs]
    sub_docs = list(db.subcategories.find({"category_id": {"$in": cat_ids}, "is_active": {"$ne": False}}))
    return {
        "category_ids": cat_ids,
        "categories": [x["name"] for x in cat_docs],
        "subcategory_ids": [str(x["_id"]) for x in sub_docs],
        "subcategories": [x["name"] for x in sub_docs],
    }
