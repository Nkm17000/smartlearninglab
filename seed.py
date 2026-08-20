import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from app.db.mongo import get_db
from app.core.security import hash_password
import uuid


def oid():
    return uuid.uuid4().hex


def seed():
    db = get_db()

    # Fresh seed: clears application collections only.
    collections = [
        "users",
        "exams",
        "subjects",
        "topics",
        "courses",
        "lessons",
        "questions",
        "mock_tests",
        "current_affairs",
        "progress",
        "mistakes",
        "notes",
        "test_results",
        "ai_conversations",
        "ai_messages",
    ]
    for c in collections:
        db[c].delete_many({})

    admin_id = oid()
    student_id = oid()
    db.users.insert_many(
        [
            {
                "_id": admin_id,
                "name": "Admin",
                "email": "admin@smartlearninglab.com",
                "password_hash": hash_password("ChangeMe123!"),
                "role": "admin",
                "created_at": datetime.utcnow(),
            },
            {
                "_id": student_id,
                "name": "Nitin",
                "email": "nitin@example.com",
                "password_hash": hash_password("Password123!"),
                "role": "student",
                "created_at": datetime.utcnow(),
            },
        ]
    )

    exam_id = oid()
    db.exams.insert_one(
        {
            "_id": exam_id,
            "name": "UPSC Civil Services",
            "description": "Free foundation preparation for UPSC CSE.",
            "short_name": "UPSC CSE",
            "is_published": True,
            "order": 1,
        }
    )

    subjects = []
    for i, (name, desc) in enumerate(
        [
            (
                "Indian Polity",
                "Constitution, Parliament, Fundamental Rights and governance.",
            ),
            ("Indian History", "Ancient, Medieval and Modern Indian History."),
            ("Geography", "Physical, Indian and World Geography."),
            ("Indian Economy", "Basic macroeconomics, banking and public finance."),
        ],
        1,
    ):
        sid = oid()
        subjects.append(
            {
                "_id": sid,
                "exam_id": exam_id,
                "name": name,
                "description": desc,
                "is_published": True,
                "order": i,
            }
        )
    db.subjects.insert_many(subjects)

    topics = []
    for s in subjects:
        for j, name in enumerate(
            {
                "Indian Polity": ["Constitution", "Fundamental Rights", "Parliament"],
                "Indian History": ["Modern India", "Freedom Movement"],
                "Geography": ["Physical Geography", "Indian Geography"],
                "Indian Economy": ["National Income", "Banking & Monetary Policy"],
            }[s["name"]],
            1,
        ):
            topics.append(
                {
                    "_id": oid(),
                    "subject_id": s["_id"],
                    "exam_id": exam_id,
                    "name": name,
                    "description": f"{name} fundamentals",
                    "is_published": True,
                    "order": j,
                }
            )
    db.topics.insert_many(topics)

    courses = []
    for t in topics:
        cid = oid()
        courses.append(
            {
                "_id": cid,
                "exam_id": exam_id,
                "subject_id": t["subject_id"],
                "topic_id": t["_id"],
                "name": f"{t['name']} Foundation",
                "description": f"Free course: {t['name']}",
                "is_published": True,
                "order": 1,
            }
        )
    db.courses.insert_many(courses)

    lessons = []
    for c in courses:
        for j in range(1, 4):
            lessons.append(
                {
                    "_id": oid(),
                    "course_id": c["_id"],
                    "name": f"Lesson {j}: {c['name']}",
                    "content": f"Study notes for {c['name']}. This is sample starter content. Replace with your own licensed/public-domain material.",
                    "order": j,
                    "is_published": True,
                }
            )
    db.lessons.insert_many(lessons)

    questions = []
    sample = [
        (
            "Which part of the Constitution deals with Fundamental Rights?",
            ["Part I", "Part II", "Part III", "Part IV"],
            2,
            "Part III contains Fundamental Rights.",
        ),
        (
            "Which institution is the lower house of Parliament?",
            ["Rajya Sabha", "Lok Sabha", "Supreme Court", "NITI Aayog"],
            1,
            "Lok Sabha is the lower house.",
        ),
        (
            "Which gas is most abundant in Earth's atmosphere?",
            ["Oxygen", "Nitrogen", "Carbon dioxide", "Hydrogen"],
            1,
            "Nitrogen is the most abundant gas.",
        ),
        (
            "Which body controls monetary policy in India?",
            ["SEBI", "RBI", "CAG", "UPSC"],
            1,
            "The RBI is India's central bank and conducts monetary policy.",
        ),
    ]
    for i, (q, opts, ans, exp) in enumerate(sample):
        topic = topics[i % len(topics)]
        questions.append(
            {
                "_id": oid(),
                "exam_id": exam_id,
                "subject_id": topic["subject_id"],
                "topic_id": topic["_id"],
                "question": q,
                "options": opts,
                "answer": ans,
                "explanation": exp,
                "difficulty": "easy",
                "is_published": True,
            }
        )
    db.questions.insert_many(questions)

    test_id = oid()
    db.mock_tests.insert_one(
        {
            "_id": test_id,
            "exam_id": exam_id,
            "name": "UPSC Foundation Mini Test",
            "description": "Starter 4-question mock test",
            "question_ids": [q["_id"] for q in questions],
            "questions": questions,
            "duration_minutes": 10,
            "is_published": True,
        }
    )

    now = datetime.utcnow()
    db.current_affairs.insert_many(
        [
            {
                "_id": oid(),
                "title": "How to use the Constitution in exam preparation",
                "content": "Starter current-affairs-style learning note. Replace with verified current content.",
                "category": "National",
                "date": now,
                "is_published": True,
            },
            {
                "_id": oid(),
                "title": "Understanding monetary policy",
                "content": "Starter economy learning note for beginners.",
                "category": "Economy",
                "date": now - timedelta(days=1),
                "is_published": True,
            },
        ]
    )

    print("Seed completed.")
    print("Database:", db.name)
    print("Admin: admin@smartlearninglab.com / ChangeMe123!")
    print("Student: nitin@example.com / Password123!")
    print("Users:", db.users.count_documents({}))
    print("Exams:", db.exams.count_documents({}))
    print("Subjects:", db.subjects.count_documents({}))
    print("Topics:", db.topics.count_documents({}))
    print("Courses:", db.courses.count_documents({}))
    print("Lessons:", db.lessons.count_documents({}))
    print("Questions:", db.questions.count_documents({}))
    print("Mock tests:", db.mock_tests.count_documents({}))


if __name__ == "__main__":
    seed()
