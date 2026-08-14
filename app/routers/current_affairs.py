from fastapi import APIRouter, Query
from app.db.mongo import get_db
from app.services.query import paginated

router = APIRouter(prefix="/current-affairs", tags=["Current Affairs"])


@router.get("")
def list_current_affairs(
    category_id: str | None = None,
    month: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    query = {"status": {"$ne": "deleted"}}
    if category_id:
        query["categoryId"] = category_id
    if month:
        query["month"] = month
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"summary": {"$regex": search, "$options": "i"}},
        ]
    return paginated(get_db().current_affairs, query, page, limit, [("publishedAt", -1)])


@router.get("/categories")
def categories():
    return list(get_db().current_affair_categories.find({"active": {"$ne": False}}, {"_id": 1, "name": 1, "code": 1}).sort("name", 1))


@router.get("/monthly/{month}")
def monthly(month: str):
    docs = list(get_db().monthly_current_affairs.find({"month": month}).sort("order", 1))
    return docs
