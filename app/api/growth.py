from datetime import datetime, timezone, timedelta
import uuid
import secrets
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.core.security import current_user, admin_user
from app.db.mongo import get_db
from app.core.cache import cache, TTL_ANALYTICS, TTL_LEADERBOARD, TTL_BOOKMARKS, TTL_CERTIFICATES, TTL_NOTIFICATIONS, TTL_BADGES, invalidate_user

router = APIRouter(prefix="/api/v1", tags=["Platform Growth"])

def now():
    return datetime.now(timezone.utc)

def uid(user):
    return str(user["_id"])

def clean(v):
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items() if k != "password_hash"}
    if isinstance(v, list):
        return [clean(x) for x in v]
    try:
        from bson import ObjectId
        if isinstance(v, ObjectId):
            return str(v)
    except Exception:
        pass
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v

def find(collection, item_id):
    db = get_db()
    x = db[collection].find_one({"_id": item_id})
    if x:
        return x
    try:
        from bson import ObjectId
        if ObjectId.is_valid(item_id):
            return db[collection].find_one({"_id": ObjectId(item_id)})
    except Exception:
        pass
    return None

def day_key(value):
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    if hasattr(value, "date"):
        return value.date().isoformat()
    return None

def user_activity_days(user_id):
    db = get_db()
    days = set()
    for collection in ("progress", "test_attempts", "enrollments", "notes", "bookmarks", "course_reviews"):
        for x in db[collection].find({"user_id": user_id}, {"created_at": 1, "updated_at": 1, "submitted_at": 1, "completed_at": 1}):
            for key in ("created_at", "updated_at", "submitted_at", "completed_at"):
                d = day_key(x.get(key))
                if d:
                    days.add(d)
    return days

def calculate_streak(user_id):
    days = user_activity_days(user_id)
    if not days:
        return {"current": 0, "best": 0, "active_today": False}
    dates = sorted({datetime.fromisoformat(x).date() for x in days})
    best = current = 1
    for i in range(1, len(dates)):
        if dates[i] == dates[i - 1] + timedelta(days=1):
            current += 1
            best = max(best, current)
        else:
            current = 1
    today = now().date()
    active_today = today.isoformat() in days
    streak = 0
    cursor = today
    while cursor.isoformat() in days:
        streak += 1
        cursor -= timedelta(days=1)
    if not active_today and (today - timedelta(days=1)).isoformat() not in days:
        streak = 0
    return {"current": streak, "best": best, "active_today": active_today}

@router.get("/analytics")
def student_analytics(user=Depends(current_user)):
    db = get_db(); user_id = uid(user)
    key = f"analytics:{user_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    progress = list(db.progress.find({"user_id": user_id, "completed": True}))
    attempts = list(db.test_attempts.find({"user_id": user_id, "status": "submitted"}))
    enrollments = db.enrollments.count_documents({"user_id": user_id, "status": "active"})
    completed_courses = 0
    course_ids = {str(x.get("course_id")) for x in progress if x.get("course_id")}
    for course_id in course_ids:
        total = db.lessons.count_documents({"course_id": course_id, "is_published": True})
        done = db.progress.count_documents({"user_id": user_id, "course_id": course_id, "completed": True})
        if total and done >= total:
            completed_courses += 1
    scores = [float(x.get("result", {}).get("percentage", 0)) for x in attempts]
    avg = round(sum(scores) / len(scores), 1) if scores else 0
    passed = sum(1 for x in attempts if x.get("result", {}).get("passed"))
    xp = len(progress) * 10 + passed * 50 + len(attempts) * 5 + completed_courses * 100
    result = {
        "courses_enrolled": enrollments,
        "courses_completed": completed_courses,
        "lessons_completed": len(progress),
        "quiz_attempts": len(attempts),
        "quizzes_passed": passed,
        "average_score": avg,
        "learning_hours": round((len(progress) * 10) / 60, 1),
        "xp": xp,
        "level": 1 + xp // 500,
        "streak": calculate_streak(user_id),
    }
    cache.set(key, result, TTL_ANALYTICS)
    return result

@router.get("/analytics/summary")
def analytics_summary(user=Depends(current_user)):
    """Single, defensive analytics payload for the student analytics page.

    IDs are normalized with $toString so legacy documents containing either
    ObjectId or string references continue to work.
    """
    user_id = uid(user)
    key = f"analytics_summary:{user_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    db = get_db()

    progress = list(db.progress.find(
        {"user_id": user_id, "completed": True},
        {"course_id": 1, "lesson_id": 1, "completed_at": 1, "updated_at": 1, "created_at": 1}
    ))
    # Legacy data may store user_id as ObjectId. Include both representations.
    try:
        from bson import ObjectId
        user_variants = [user_id, ObjectId(user_id)] if ObjectId.is_valid(user_id) else [user_id]
    except Exception:
        user_variants = [user_id]

    if not progress:
        progress = list(db.progress.find(
            {"user_id": {"$in": user_variants}, "completed": True},
            {"course_id": 1, "lesson_id": 1, "completed_at": 1, "updated_at": 1, "created_at": 1}
        ))

    attempts = list(db.test_attempts.find(
        {"user_id": {"$in": user_variants}, "status": "submitted"},
        {"result": 1, "submitted_at": 1, "created_at": 1, "updated_at": 1}
    ))

    enrollments = db.enrollments.count_documents({
        "user_id": {"$in": user_variants},
        "status": "active"
    })

    scores = [
        float((x.get("result") or {}).get("percentage", 0) or 0)
        for x in attempts
    ]
    passed = sum(
        1 for x in attempts
        if bool((x.get("result") or {}).get("passed"))
    )
    average_score = round(sum(scores) / len(scores), 1) if scores else 0

    completed_course_ids = list({
        str(x.get("course_id"))
        for x in progress
        if x.get("course_id") is not None
    })

    completed_courses = 0
    if completed_course_ids:
        lesson_totals = {
            str(x["_id"]): int(x["n"])
            for x in db.lessons.aggregate([
                {"$match": {
                    "is_published": True,
                    "$expr": {"$in": [{"$toString": "$course_id"}, completed_course_ids]}
                }},
                {"$group": {"_id": {"$toString": "$course_id"}, "n": {"$sum": 1}}}
            ])
        }

        progress_totals = {
            str(x["_id"]): int(x["n"])
            for x in db.progress.aggregate([
                {"$match": {
                    "completed": True,
                    "user_id": {"$in": user_variants},
                    "$expr": {"$in": [{"$toString": "$course_id"}, completed_course_ids]}
                }},
                {"$group": {"_id": {"$toString": "$course_id"}, "n": {"$sum": 1}}}
            ])
        }
        completed_courses = sum(
            1 for course_id, total in lesson_totals.items()
            if total > 0 and progress_totals.get(course_id, 0) >= total
        )

    xp = len(progress) * 10 + passed * 50 + len(attempts) * 5 + completed_courses * 100

    # Activity collection is optional in older databases.
    recent_activity = []
    try:
        recent_activity = [
            clean(x) for x in db.activity_events.find(
                {"user_id": {"$in": user_variants}},
                {"created_at": 1, "type": 1, "action": 1, "title": 1}
            ).sort("created_at", -1).limit(30)
        ]
    except Exception:
        recent_activity = []

    result = {
        "basic": {
            "courses_enrolled": enrollments,
            "courses_completed": completed_courses,
            "lessons_completed": len(progress),
            "quiz_attempts": len(attempts),
            "quizzes_passed": passed,
            "average_score": average_score,
            "learning_hours": round((len(progress) * 10) / 60, 1),
            "xp": xp,
            "level": 1 + xp // 500,
            "streak": calculate_streak(user_id),
        },
        "advanced": {
            "courses_enrolled": enrollments,
            "lessons_completed": len(progress),
            "tests_taken": len(attempts),
            "average_score": round(sum(scores) / len(scores), 2) if scores else 0,
            "recent_activity": recent_activity,
        },
    }
    cache.set(key, result, TTL_ANALYTICS)
    return result


@router.get("/leaderboard")
def leaderboard(limit: int = 20, user=Depends(current_user)):
    """Return a resilient, cached student leaderboard.

    This endpoint intentionally avoids MongoDB operators that can fail on
    legacy/mixed schemas. Activity collections are optional: if progress or
    test_attempts contain incompatible legacy data, the leaderboard still
    returns students with the activity that could be read.
    """
    db = get_db()
    user_id = str(user.get("_id", ""))

    try:
        safe_limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        safe_limit = 20

    cache_key = "leaderboard:all:v4"
    cached = cache.get(cache_key)
    if cached is not None:
        rows = cached.get("rows") or []
        me = next((r for r in rows if str(r.get("id")) == user_id), None)
        return {
            "items": rows[:safe_limit],
            "me": me,
            "total_students": len(rows),
        }

    # --------------------------------------------------------
    # 1. Read students defensively.
    # --------------------------------------------------------
    students = []
    try:
        cursor = db.users.find(
            {"role": "student"},
            {"_id": 1, "name": 1, "email": 1, "is_active": 1},
        ).limit(2000)
        students = list(cursor)
    except Exception:
        # Some older deployments may have a different role representation.
        # Fall back to users that are not administrative accounts.
        try:
            cursor = db.users.find(
                {"role": {"$nin": ["admin", "root_admin", "content_admin", "instructor", "support_admin"]}},
                {"_id": 1, "name": 1, "email": 1, "is_active": 1},
            ).limit(2000)
            students = list(cursor)
        except Exception:
            students = []

    # Never make the page fail just because leaderboard data is unavailable.
    if not students:
        result = {"items": [], "me": None, "total_students": 0}
        cache.set(cache_key, {"rows": []}, TTL_LEADERBOARD)
        return result

    # --------------------------------------------------------
    # 2. Build both ObjectId and string forms of every user id.
    # --------------------------------------------------------
    raw_ids = [x.get("_id") for x in students if x.get("_id") is not None]
    lookup_ids = []
    seen = set()
    for value in raw_ids:
        candidates = [value, str(value)]
        for candidate in candidates:
            marker = repr(candidate)
            if marker not in seen:
                seen.add(marker)
                lookup_ids.append(candidate)

    # --------------------------------------------------------
    # 3. Aggregate completed lessons.
    # --------------------------------------------------------
    progress_counts = {}
    try:
        for item in db.progress.aggregate([
            {"$match": {
                "completed": True,
                "user_id": {"$in": lookup_ids},
            }},
            {"$group": {
                "_id": "$user_id",
                "count": {"$sum": 1},
            }},
        ]):
            key = str(item.get("_id")) if item.get("_id") is not None else None
            if key:
                progress_counts[key] = progress_counts.get(key, 0) + int(item.get("count", 0) or 0)
    except Exception:
        # Legacy/missing progress collection must not break leaderboard.
        progress_counts = {}

    # --------------------------------------------------------
    # 4. Aggregate submitted tests.
    # --------------------------------------------------------
    attempt_stats = {}
    try:
        for item in db.test_attempts.aggregate([
            {"$match": {
                "status": "submitted",
                "user_id": {"$in": lookup_ids},
            }},
            {"$group": {
                "_id": "$user_id",
                "count": {"$sum": 1},
                "passed": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$result.passed", True]},
                            1,
                            0,
                        ]
                    }
                },
            }},
        ]):
            key = str(item.get("_id")) if item.get("_id") is not None else None
            if key:
                attempt_stats[key] = {
                    "count": int(item.get("count", 0) or 0),
                    "passed": int(item.get("passed", 0) or 0),
                }
    except Exception:
        attempt_stats = {}

    # --------------------------------------------------------
    # 5. Build deterministic ranking.
    # --------------------------------------------------------
    rows = []
    for student in students:
        sid = str(student.get("_id", ""))
        if not sid:
            continue

        # Treat an explicit inactive flag as inactive, but preserve legacy
        # users where the field is absent.
        if student.get("is_active") is False:
            continue

        lessons = progress_counts.get(sid, 0)
        stats = attempt_stats.get(sid, {"count": 0, "passed": 0})
        attempts = stats.get("count", 0)
        passed = stats.get("passed", 0)
        xp = (lessons * 10) + (passed * 50) + (attempts * 5)

        rows.append({
            "id": sid,
            "name": str(student.get("name") or "Student"),
            "xp": int(xp),
            "lessons": int(lessons),
            "tests": int(attempts),
        })

    rows.sort(key=lambda row: (
        -row["xp"],
        row["name"].lower(),
        row["id"],
    ))

    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank

    cache.set(cache_key, {"rows": rows}, TTL_LEADERBOARD)

    me = next((r for r in rows if r["id"] == user_id), None)
    return {
        "items": rows[:safe_limit],
        "me": me,
        "total_students": len(rows),
    }

@router.get("/notifications")
def notifications(user=Depends(current_user)):
    user_id = uid(user); key = f"notifications:{user_id}"
    cached = cache.get(key)
    if cached is not None: return cached
    result = [clean(x) for x in get_db().notifications.find({"user_id": user_id}).sort("created_at", -1).limit(50)]
    cache.set(key, result, TTL_NOTIFICATIONS)
    return result

@router.post("/notifications/read")
def mark_notifications_read(data: dict, user=Depends(current_user)):
    db = get_db(); user_id = uid(user)
    notification_id = data.get("id")
    if notification_id:
        db.notifications.update_one({"_id": notification_id, "user_id": user_id}, {"$set": {"read": True}})
        cache.delete_prefix(f"notifications:{user_id}")
    else:
        db.notifications.update_many({"user_id": user_id}, {"$set": {"read": True}})
        cache.delete_prefix(f"notifications:{user_id}")
    return {"message": "Notifications updated"}

@router.get("/bookmarks")
def bookmarks(user=Depends(current_user)):
    user_id = uid(user); key = f"bookmarks:{user_id}"
    cached = cache.get(key)
    if cached is not None: return cached
    result = [clean(x) for x in get_db().bookmarks.find({"user_id": user_id}).sort("created_at", -1)]
    cache.set(key, result, TTL_BOOKMARKS)
    return result

@router.post("/bookmarks")
def add_bookmark(data: dict, user=Depends(current_user)):
    item_type = data.get("item_type", "lesson")
    item_id = str(data.get("item_id", ""))
    if not item_id:
        raise HTTPException(422, "item_id is required")
    db = get_db(); user_id = uid(user)
    existing = db.bookmarks.find_one({"user_id": user_id, "item_type": item_type, "item_id": item_id})
    if existing:
        return clean(existing)
    d = {"_id": uuid.uuid4().hex, "user_id": user_id, "item_type": item_type, "item_id": item_id, "title": data.get("title", ""), "created_at": now()}
    db.bookmarks.insert_one(d)
    cache.delete_prefix(f"bookmarks:{user_id}")
    cache.delete_prefix(f"study_assistance:{user_id}")
    cache.delete_prefix(f"course:overview:{user_id}:")
    return clean(d)

@router.delete("/bookmarks/{bookmark_id}")
def delete_bookmark(bookmark_id: str, user=Depends(current_user)):
    result = get_db().bookmarks.delete_one({"_id": bookmark_id, "user_id": uid(user)})
    if not result.deleted_count:
        raise HTTPException(404, "Bookmark not found")
    cache.delete_prefix(f"bookmarks:{uid(user)}")
    cache.delete_prefix(f"study_assistance:{uid(user)}")
    cache.delete_prefix(f"course:overview:{uid(user)}:")
    return {"message": "Bookmark removed"}

@router.get("/courses/{course_id}/reviews")
def course_reviews(course_id: str, user=Depends(current_user)):
    return [clean(x) for x in get_db().course_reviews.find({"course_id": course_id}).sort("created_at", -1).limit(100)]

@router.post("/courses/{course_id}/reviews")
def add_course_review(course_id: str, data: dict, user=Depends(current_user)):
    db = get_db()
    user_id = uid(user)
    course_id = str(course_id).strip()

    # The course id can be stored either as a string or a Mongo ObjectId.
    # Use the existing helper so both forms are supported.
    course = find("courses", course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Validate rating without allowing ValueError to become a 500 response.
    try:
        rating = int(data.get("rating", 0))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail="Rating must be a number between 1 and 5"
        )

    if rating < 1 or rating > 5:
        raise HTTPException(
            status_code=422,
            detail="Rating must be between 1 and 5"
        )

    review_text = str(data.get("review", "")).strip()

    if not review_text:
        raise HTTPException(
            status_code=422,
            detail="Review cannot be empty"
        )

    if len(review_text) > 2000:
        raise HTTPException(
            status_code=422,
            detail="Review cannot exceed 2000 characters"
        )

    review_doc = {
        "_id": uuid.uuid4().hex,
        "course_id": course_id,
        "user_id": user_id,
        "user_name": user.get("name", "Student"),
        "rating": rating,
        "review": review_text,
        "created_at": now(),
    }

    # One review per student/course. Submitting again updates that review.
    db.course_reviews.update_one(
        {"course_id": course_id, "user_id": user_id},
        {"$set": review_doc},
        upsert=True,
    )

    reviews = list(
        db.course_reviews.find({"course_id": course_id})
    )

    average_rating = (
        round(
            sum(int(x.get("rating", 0)) for x in reviews)
            / len(reviews),
            1,
        )
        if reviews
        else 0
    )

    db.courses.update_one(
        {"_id": course.get("_id")},
        {
            "$set": {
                "rating": average_rating,
                "review_count": len(reviews),
            }
        },
    )

    return clean(review_doc)

@router.get("/certificates")
def certificates(user=Depends(current_user)):
    user_id = uid(user); key = f"certificates:{user_id}"
    cached = cache.get(key)
    if cached is not None: return cached
    result = [clean(x) for x in get_db().certificates.find({"user_id": user_id}).sort("issued_at", -1)]
    cache.set(key, result, TTL_CERTIFICATES)
    return result

@router.post("/certificates/course/{course_id}/issue")
def issue_certificate(course_id: str, user=Depends(current_user)):
    db = get_db(); user_id = uid(user)
    course = find("courses", course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    total = db.lessons.count_documents({"course_id": course_id, "is_published": True})
    done = db.progress.count_documents({"user_id": user_id, "course_id": course_id, "completed": True})
    if total and done < total:
        raise HTTPException(400, "Complete all published lessons before requesting the certificate")
    existing = db.certificates.find_one({"user_id": user_id, "course_id": course_id})
    if existing:
        return clean(existing)
    certificate_id = f"SLL-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    d = {"_id": uuid.uuid4().hex, "certificate_id": certificate_id, "user_id": user_id, "course_id": course_id, "course_name": course.get("name") or course.get("title"), "student_name": user.get("name", "Student"), "issued_at": now()}
    db.certificates.insert_one(d)
    cache.delete_prefix(f"certificates:{user_id}")
    cache.delete_prefix(f"course:overview:{user_id}:")
    return clean(d)

@router.post("/certificates/{certificate_id}/access")
def certificate_access(certificate_id: str, user=Depends(current_user)):
    """Issue a short-lived token so the PDF can be opened/downloaded by a browser."""
    db = get_db()
    cert = db.certificates.find_one({
        "certificate_id": certificate_id,
        "user_id": uid(user),
    })
    if not cert:
        raise HTTPException(404, "Certificate not found")

    token = secrets.token_urlsafe(32)
    expires = now() + timedelta(minutes=10)
    db.certificate_download_tokens.insert_one({
        "_id": uuid.uuid4().hex,
        "token": token,
        "certificate_id": certificate_id,
        "user_id": uid(user),
        "expires_at": expires,
    })
    return {
        "preview_token": token,
        "download_token": token,
        "expires_at": expires.isoformat(),
    }


def _certificate_by_download_token(certificate_id: str, token: str):
    db = get_db()
    record = db.certificate_download_tokens.find_one({
        "token": token,
        "certificate_id": certificate_id,
        "expires_at": {"$gt": now()},
    })
    if not record:
        raise HTTPException(401, "Certificate download link expired. Please request a new link.")
    cert = db.certificates.find_one({
        "certificate_id": certificate_id,
        "user_id": record["user_id"],
    })
    if not cert:
        raise HTTPException(404, "Certificate not found")
    return cert


def _certificate_pdf_from_cert(cert, disposition: str):
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas
    except ImportError:
        raise HTTPException(503, "Certificate PDF support is not installed")

    buffer = BytesIO()
    page = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=page)
    width, height = page

    c.setFillColorRGB(0.98, 0.99, 1)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setStrokeColorRGB(0.91, 0.12, 0.39)
    c.setLineWidth(5)
    c.rect(25, 25, width - 50, height - 50, fill=0, stroke=1)
    c.setStrokeColorRGB(0.15, 0.20, 0.35)
    c.setLineWidth(1)
    c.rect(38, 38, width - 76, height - 76, fill=0, stroke=1)

    c.setFillColorRGB(0.07, 0.09, 0.15)
    c.setFont("Helvetica-Bold", 27)
    c.drawCentredString(width / 2, height - 105, "SMART LEARNING LAB")
    c.setFillColorRGB(0.91, 0.12, 0.39)
    c.setFont("Helvetica-Bold", 21)
    c.drawCentredString(width / 2, height - 155, "CERTIFICATE OF COMPLETION")
    c.setFillColorRGB(0.25, 0.28, 0.34)
    c.setFont("Helvetica", 13)
    c.drawCentredString(width / 2, height - 205, "This certificate is proudly presented to")
    c.setFillColorRGB(0.07, 0.09, 0.15)
    c.setFont("Helvetica-Bold", 27)
    c.drawCentredString(width / 2, height - 250, cert.get("student_name", "Student"))
    c.setFillColorRGB(0.25, 0.28, 0.34)
    c.setFont("Helvetica", 13)
    c.drawCentredString(width / 2, height - 292, "for successfully completing")
    c.setFillColorRGB(0.91, 0.12, 0.39)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 330, cert.get("course_name", "Course"))
    c.setFillColorRGB(0.25, 0.28, 0.34)
    c.setFont("Helvetica", 10)
    c.drawCentredString(
        width / 2, 70,
        f"Certificate ID: {cert.get('certificate_id')}   |   Issued: {day_key(cert.get('issued_at'))}"
    )
    c.save()
    buffer.seek(0)
    filename = f"{cert.get('certificate_id')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


def _certificate_pdf_response(certificate_id: str, user_id: str, disposition: str):
    cert = get_db().certificates.find_one({
        "certificate_id": certificate_id,
        "user_id": user_id
    })
    if not cert:
        raise HTTPException(404, "Certificate not found")
    return _certificate_pdf_from_cert(cert, disposition)


@router.get("/certificates/{certificate_id}/preview")
def certificate_preview(certificate_id: str, user=Depends(current_user)):
    cert = get_db().certificates.find_one({"certificate_id": certificate_id, "user_id": uid(user)})
    if not cert:
        raise HTTPException(404, "Certificate not found")
    return _certificate_pdf_from_cert(cert, "inline")


@router.get("/certificates/{certificate_id}/pdf")
def certificate_pdf(certificate_id: str, user=Depends(current_user)):
    cert = get_db().certificates.find_one({"certificate_id": certificate_id, "user_id": uid(user)})
    if not cert:
        raise HTTPException(404, "Certificate not found")
    return _certificate_pdf_from_cert(cert, "attachment")


@router.get("/certificates/public/{certificate_id}/preview")
def certificate_public_preview(certificate_id: str, token: str):
    cert = _certificate_by_download_token(certificate_id, token)
    return _certificate_pdf_from_cert(cert, "inline")


@router.get("/certificates/public/{certificate_id}/download")
def certificate_public_download(certificate_id: str, token: str):
    cert = _certificate_by_download_token(certificate_id, token)
    return _certificate_pdf_from_cert(cert, "attachment")


@router.get("/badges")
def badges(user=Depends(current_user)):
    user_id = uid(user); key = f"badges:{user_id}"
    cached = cache.get(key)
    if cached is not None: return cached
    a = student_analytics(user)
    items = []
    if a["lessons_completed"] >= 1: items.append({"code":"first_lesson","name":"First Lesson","description":"Completed your first lesson","icon":"📖"})
    if a["lessons_completed"] >= 10: items.append({"code":"ten_lessons","name":"10 Lessons","description":"Completed ten lessons","icon":"🎯"})
    if a["quiz_attempts"] >= 5: items.append({"code":"test_taker","name":"Test Taker","description":"Attempted five tests","icon":"📝"})
    if a["streak"]["current"] >= 7: items.append({"code":"seven_day_streak","name":"7 Day Streak","description":"Learned for seven days in a row","icon":"🔥"})
    if a["xp"] >= 500: items.append({"code":"rising_star","name":"Rising Star","description":"Earned 500 XP","icon":"⭐"})
    cache.set(key, items, TTL_BADGES)
    return items

@router.get("/admin/analytics")
def admin_analytics(user=Depends(admin_user)):
    db = get_db()
    courses = db.courses.count_documents({})
    published = db.courses.count_documents({"is_published": True})
    students = db.users.count_documents({"role": "student"})
    enrollments = db.enrollments.count_documents({"status": "active"})
    attempts = db.test_attempts.count_documents({"status": "submitted"})
    reviews = db.course_reviews.count_documents({})
    scores = [float(x.get("result", {}).get("percentage", 0)) for x in db.test_attempts.find({"status": "submitted"}, {"result": 1})]
    avg = round(sum(scores) / len(scores), 1) if scores else 0
    popular = []
    for c in db.courses.find({"is_published": True}).sort("students_count", -1).limit(8):
        popular.append({"id": str(c["_id"]), "name": c.get("name", c.get("title", "Course")), "students": c.get("students_count", 0), "rating": c.get("rating", 0)})
    return {"courses": courses, "published_courses": published, "students": students, "enrollments": enrollments, "quiz_attempts": attempts, "reviews": reviews, "average_quiz_score": avg, "popular_courses": popular}
