from datetime import datetime, timezone, timedelta
import uuid
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.core.security import current_user, admin_user
from app.db.mongo import get_db

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
    return {
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

@router.get("/leaderboard")
def leaderboard(limit: int = 20, user=Depends(current_user)):
    db = get_db()
    students = list(db.users.find({"role": "student", "is_active": True}, {"password_hash": 0}).limit(500))
    rows = []
    for student in students:
        sid = str(student["_id"])
        lessons = db.progress.count_documents({"user_id": sid, "completed": True})
        attempts = list(db.test_attempts.find({"user_id": sid, "status": "submitted"}))
        passed = sum(1 for a in attempts if a.get("result", {}).get("passed"))
        score = lessons * 10 + passed * 50 + len(attempts) * 5
        rows.append({"id": sid, "name": student.get("name", "Student"), "xp": score, "lessons": lessons, "tests": len(attempts)})
    rows.sort(key=lambda x: x["xp"], reverse=True)
    for i, row in enumerate(rows, 1):
        row["rank"] = i
    return {"items": rows[:max(1, min(limit, 100))], "me": next((x for x in rows if x["id"] == uid(user)), None)}

@router.get("/notifications")
def notifications(user=Depends(current_user)):
    return [clean(x) for x in get_db().notifications.find({"user_id": uid(user)}).sort("created_at", -1).limit(50)]

@router.post("/notifications/read")
def mark_notifications_read(data: dict, user=Depends(current_user)):
    db = get_db(); user_id = uid(user)
    notification_id = data.get("id")
    if notification_id:
        db.notifications.update_one({"_id": notification_id, "user_id": user_id}, {"$set": {"read": True}})
    else:
        db.notifications.update_many({"user_id": user_id}, {"$set": {"read": True}})
    return {"message": "Notifications updated"}

@router.get("/bookmarks")
def bookmarks(user=Depends(current_user)):
    return [clean(x) for x in get_db().bookmarks.find({"user_id": uid(user)}).sort("created_at", -1)]

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
    return clean(d)

@router.delete("/bookmarks/{bookmark_id}")
def delete_bookmark(bookmark_id: str, user=Depends(current_user)):
    result = get_db().bookmarks.delete_one({"_id": bookmark_id, "user_id": uid(user)})
    if not result.deleted_count:
        raise HTTPException(404, "Bookmark not found")
    return {"message": "Bookmark removed"}

@router.get("/courses/{course_id}/reviews")
def course_reviews(course_id: str, user=Depends(current_user)):
    return [clean(x) for x in get_db().course_reviews.find({"course_id": course_id}).sort("created_at", -1).limit(100)]

@router.post("/courses/{course_id}/reviews")
def add_course_review(course_id: str, data: dict, user=Depends(current_user)):
    db = get_db(); user_id = uid(user)
    if not find("courses", course_id):
        raise HTTPException(404, "Course not found")
    rating = int(data.get("rating", 0))
    if rating < 1 or rating > 5:
        raise HTTPException(422, "Rating must be between 1 and 5")
    d = {"_id": uuid.uuid4().hex, "course_id": course_id, "user_id": user_id, "user_name": user.get("name", "Student"), "rating": rating, "review": str(data.get("review", ""))[:2000], "created_at": now()}
    db.course_reviews.update_one({"course_id": course_id, "user_id": user_id}, {"$set": d}, upsert=True)
    reviews = list(db.course_reviews.find({"course_id": course_id}))
    avg = round(sum(int(x.get("rating", 0)) for x in reviews) / len(reviews), 1) if reviews else 0
    db.courses.update_one({"_id": find("courses", course_id)["_id"]}, {"$set": {"rating": avg, "review_count": len(reviews)}})
    return clean(d)

@router.get("/certificates")
def certificates(user=Depends(current_user)):
    return [clean(x) for x in get_db().certificates.find({"user_id": uid(user)}).sort("issued_at", -1)]

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
    return clean(d)

@router.get("/certificates/{certificate_id}/pdf")
def certificate_pdf(certificate_id: str, user=Depends(current_user)):
    cert = get_db().certificates.find_one({"certificate_id": certificate_id, "user_id": uid(user)})
    if not cert:
        raise HTTPException(404, "Certificate not found")
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas
    except ImportError:
        raise HTTPException(503, "Certificate PDF support is not installed")
    buffer = BytesIO(); page = landscape(A4); c = canvas.Canvas(buffer, pagesize=page)
    width, height = page
    c.setStrokeColorRGB(0.91, 0.12, 0.39); c.setLineWidth(4); c.rect(28, 28, width-56, height-56)
    c.setFillColorRGB(0.07, 0.09, 0.15); c.setFont("Helvetica-Bold", 28); c.drawCentredString(width/2, height-110, "SMART LEARNING LAB")
    c.setFont("Helvetica-Bold", 20); c.setFillColorRGB(0.91, 0.12, 0.39); c.drawCentredString(width/2, height-165, "Certificate of Completion")
    c.setFillColorRGB(0.2,0.2,0.2); c.setFont("Helvetica", 14); c.drawCentredString(width/2, height-220, "This certificate is proudly presented to")
    c.setFont("Helvetica-Bold", 25); c.drawCentredString(width/2, height-270, cert.get("student_name", "Student"))
    c.setFont("Helvetica", 14); c.drawCentredString(width/2, height-320, "for successfully completing")
    c.setFont("Helvetica-Bold", 20); c.drawCentredString(width/2, height-360, cert.get("course_name", "Course"))
    c.setFont("Helvetica", 11); c.drawCentredString(width/2, 90, f"Certificate ID: {cert.get('certificate_id')}   |   Issued: {day_key(cert.get('issued_at'))}")
    c.save(); buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={certificate_id}.pdf"})

@router.get("/badges")
def badges(user=Depends(current_user)):
    a = student_analytics(user)
    items = []
    if a["lessons_completed"] >= 1: items.append({"code":"first_lesson","name":"First Lesson","description":"Completed your first lesson","icon":"📖"})
    if a["lessons_completed"] >= 10: items.append({"code":"ten_lessons","name":"10 Lessons","description":"Completed ten lessons","icon":"🎯"})
    if a["quiz_attempts"] >= 5: items.append({"code":"test_taker","name":"Test Taker","description":"Attempted five tests","icon":"📝"})
    if a["streak"]["current"] >= 7: items.append({"code":"seven_day_streak","name":"7 Day Streak","description":"Learned for seven days in a row","icon":"🔥"})
    if a["xp"] >= 500: items.append({"code":"rising_star","name":"Rising Star","description":"Earned 500 XP","icon":"⭐"})
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
