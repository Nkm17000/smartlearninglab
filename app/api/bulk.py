from datetime import datetime, timezone
import io, uuid, json
from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File, Form
from app.core.security import admin_user
from app.db.mongo import get_db
from app.api.media import COURSE_CATEGORIES, upload_bytes
from app.services.pdf_course_importer import build_course_from_pdf

router = APIRouter(prefix="/api/v1/admin/bulk", tags=["Admin Bulk Content"])

def now(): return datetime.now(timezone.utc)
def uid(user): return str(user["_id"])

def clean(v):
    if isinstance(v, dict): return {k: clean(x) for k,x in v.items()}
    if isinstance(v, list): return [clean(x) for x in v]
    try:
        from bson import ObjectId
        if isinstance(v,ObjectId): return str(v)
    except Exception: pass
    return v.isoformat() if hasattr(v,"isoformat") else v

def require_category(category):
    category = str(category or "General").strip()
    if category not in COURSE_CATEGORIES:
        raise HTTPException(422, f"Unsupported course category. Choose one of: {', '.join(COURSE_CATEGORIES)}")
    return category

def require_quiz_category(category):
    # Quiz categories are intentionally more flexible than course categories.
    # A quiz may be tagged as English, Grammar, CAT, Java, Banking, etc.
    value = str(category or "General").strip()
    if not value:
        return "General"
    if len(value) > 80:
        raise HTTPException(422, "Quiz category must be 80 characters or fewer")
    return value

def validate_questions(questions):
    if not isinstance(questions, list) or not questions:
        raise HTTPException(422, "At least one question is required")

    out = []
    for i, q in enumerate(questions, 1):
        if not isinstance(q, dict):
            raise HTTPException(422, f"Question {i} must be a JSON object")

        question = str(q.get("question", "")).strip()
        options = q.get("options")

        if not question:
            raise HTTPException(422, f"Question {i}: question text is empty")
        if not isinstance(options, list) or len(options) < 2:
            raise HTTPException(422, f"Question {i}: provide at least two options")

        normalized_options = [str(x).strip() for x in options]
        if any(not x for x in normalized_options):
            raise HTTPException(422, f"Question {i}: options cannot be empty")
        if len(set(x.casefold() for x in normalized_options)) != len(normalized_options):
            raise HTTPException(422, f"Question {i}: duplicate options are not allowed")

        correct = q.get("correct_answer", q.get("answer", 0))
        if isinstance(correct, str):
            c = correct.strip()
            # Support A/B/C/D, option text, and numeric strings.
            if len(c) == 1 and c.upper() in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                correct = ord(c.upper()) - 65
            elif c in normalized_options:
                correct = normalized_options.index(c)
            else:
                try:
                    correct = int(c)
                except Exception:
                    raise HTTPException(422, f"Question {i}: invalid correct_answer '{c}'")

        try:
            correct = int(correct)
        except Exception:
            raise HTTPException(422, f"Question {i}: correct_answer must be a zero-based option index")

        if not 0 <= correct < len(normalized_options):
            raise HTTPException(422, f"Question {i}: correct_answer {correct} is outside options 0-{len(normalized_options)-1}")

        try:
            marks = int(q.get("marks", 1) or 1)
            negative_marks = float(q.get("negative_marks", 0) or 0)
        except (TypeError, ValueError):
            raise HTTPException(422, f"Question {i}: marks and negative_marks must be numeric")

        difficulty = str(q.get("difficulty", "medium")).strip().lower() or "medium"
        if difficulty not in {"easy", "medium", "hard"}:
            difficulty = "medium"

        tags = q.get("tags", []) or []
        if not isinstance(tags, list):
            tags = [str(tags)]

        out.append({
            "_id": uuid.uuid4().hex,
            "question": question,
            "question_type": str(q.get("question_type", "mcq")),
            "options": normalized_options,
            "correct_answer": correct,
            "answer": correct,
            "difficulty": difficulty,
            "marks": max(1, marks),
            "negative_marks": max(0, negative_marks),
            "explanation": str(q.get("explanation", "")).strip(),
            "tags": tags,
            "is_published": False,
        })
    return out

def normalize_quiz_documents(payload):
    """Accept one quiz object, a list of quiz objects, or {"quizzes": [...]}.

    The important rule for bulk import is one input quiz object == one quiz draft.
    Questions inside that object belong only to that quiz.
    """
    if isinstance(payload, dict) and isinstance(payload.get("quizzes"), list):
        documents = payload["quizzes"]
    elif isinstance(payload, list):
        documents = payload
    elif isinstance(payload, dict):
        documents = [payload]
    else:
        raise HTTPException(422, "Quiz JSON must be one quiz object, an array of quiz objects, or an object containing a 'quizzes' array")

    if not documents:
        raise HTTPException(422, "At least one quiz is required")
    if len(documents) > 500:
        raise HTTPException(422, "A single bulk upload can contain at most 500 quizzes")

    normalized = []
    seen_titles = set()
    for index, document in enumerate(documents, 1):
        if not isinstance(document, dict):
            raise HTTPException(422, f"Quiz {index} must be a JSON object")

        title = str(document.get("title", document.get("name", ""))).strip()
        if not title:
            raise HTTPException(422, f"Quiz {index}: title is required")
        if len(title) > 200:
            raise HTTPException(422, f"Quiz {index}: title must be 200 characters or fewer")

        duplicate_key = title.casefold()
        if duplicate_key in seen_titles:
            raise HTTPException(422, f"Quiz {index}: duplicate quiz title '{title}' in this upload")
        seen_titles.add(duplicate_key)

        questions = validate_questions(document.get("questions"))
        try:
            duration = int(document.get("duration_minutes", max(15, len(questions) * 2)) or 15)
            passing = int(document.get("passing_percentage", 60) or 60)
            max_attempts = int(document.get("max_attempts", 3) or 3)
        except (TypeError, ValueError):
            raise HTTPException(422, f"Quiz {index}: duration_minutes, passing_percentage and max_attempts must be numbers")

        if duration < 1 or duration > 600:
            raise HTTPException(422, f"Quiz {index}: duration_minutes must be between 1 and 600")
        if passing < 0 or passing > 100:
            raise HTTPException(422, f"Quiz {index}: passing_percentage must be between 0 and 100")
        if max_attempts < 1 or max_attempts > 100:
            raise HTTPException(422, f"Quiz {index}: max_attempts must be between 1 and 100")

        topic = str(
            document.get("topic")
            or document.get("topic_name")
            or document.get("module")
            or ""
        ).strip()
        if not topic and " - " in title:
            topic = title.split(" - ", 1)[1].strip()

        normalized.append({
            "source_index": index,
            "title": title,
            "description": str(document.get("description", "")).strip(),
            "category": require_quiz_category(document.get("category", "General")),
            "course_id": document.get("course_id"),
            "module_id": document.get("module_id"),
            "topic": topic,
            "duration_minutes": duration,
            "passing_percentage": passing,
            "max_attempts": max_attempts,
            "questions": questions,
        })

    return normalized


def create_quiz_drafts(payload, user):
    """Validate the complete payload before writing anything to MongoDB."""
    documents = normalize_quiz_documents(payload)
    db = get_db()
    created = []

    # All validation is completed above before the first insert. This prevents a
    # malformed topic 17 from being discovered after topics 1-16 were inserted.
    for document in documents:
        qids = []
        for question in document["questions"]:
            question["created_at"] = now()
            question["created_by"] = uid(user)
            db.questions.insert_one(question)
            qids.append(question["_id"])

        quiz_id = uuid.uuid4().hex
        quiz = {
            "_id": quiz_id,
            "title": document["title"],
            "name": document["title"],
            "description": document["description"],
            "course_id": document["course_id"],
            "module_id": document["module_id"],
            "topic": document["topic"],
            "duration_minutes": document["duration_minutes"],
            "passing_percentage": document["passing_percentage"],
            "max_attempts": document["max_attempts"],
            "question_ids": qids,
            "category": document["category"],
            "is_published": False,
            "created_at": now(),
            "updated_at": now(),
            "created_by": uid(user),
            "bulk_imported": True,
        }
        db.quizzes.insert_one(quiz)
        created.append({
            "quiz": clean(quiz),
            "question_count": len(qids),
            "source_index": document["source_index"],
            "topic": document["topic"],
        })

    total_questions = sum(x["question_count"] for x in created)
    if len(created) == 1:
        return {
            "quiz": created[0]["quiz"],
            "quizzes": [created[0]["quiz"]],
            "created_quizzes": created,
            "quiz_count": 1,
            "question_count": total_questions,
            "total_question_count": total_questions,
            "message": "1 quiz draft created. Review it in Test Series before publishing.",
        }

    return {
        "quizzes": [x["quiz"] for x in created],
        "created_quizzes": created,
        "quiz_count": len(created),
        "question_count": total_questions,
        "total_question_count": total_questions,
        "message": f"{len(created)} quiz drafts created — one quiz for each topic in the uploaded JSON. Review them in Test Series before publishing.",
    }


@router.post("/quiz")
def bulk_quiz(data: object = Body(...), user=Depends(admin_user)):
    return create_quiz_drafts(data, user)


@router.post("/quiz-file")
async def bulk_quiz_file(file: UploadFile = File(...), user=Depends(admin_user)):
    if not file.filename:
        raise HTTPException(422, "JSON file is required")
    if not file.filename.lower().endswith((".json", ".txt")):
        raise HTTPException(422, "Upload a .json file (a .txt file containing valid JSON is also supported)")

    raw = await file.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "Quiz JSON file is too large. Maximum supported size is 20 MB.")

    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, f"Invalid JSON file: {exc}")

    return create_quiz_drafts(payload, user)


@router.post("/course-pdf")
async def bulk_course_pdf(file:UploadFile=File(...),title:str=Form(""),category:str=Form("General"),level:str=Form("Beginner"),language:str=Form("English"),user=Depends(admin_user)):
    if not file.filename: raise HTTPException(422,"PDF file is required")
    if not file.filename.lower().endswith(".pdf"): raise HTTPException(422,"Only PDF files are supported")
    category=require_category(category)
    raw=await file.read()
    if len(raw)>100*1024*1024: raise HTTPException(413,"PDF is too large. Maximum supported size is 100 MB.")

    try: generated=build_course_from_pdf(raw,file.filename)
    except Exception as e:
        raise HTTPException(422,f"Unable to analyse this PDF: {e}")
    if generated.get("status") == "needs_ocr":
        raise HTTPException(422,generated.get("reason","This PDF requires OCR before it can become editable lessons."))
    if generated.get("status") != "ok":
        raise HTTPException(422,generated.get("reason","This PDF does not contain enough course content."))

    modules=[m for m in generated.get("modules",[]) if m.get("lessons")]
    if not modules or not any(m.get("lessons") for m in modules):
        raise HTTPException(422,"No usable lesson content was found in this PDF. Upload the complete educational PDF.")

    db=get_db()
    try:
        media_id, media_filename, media_content_type, media_kind, storage_key = upload_bytes(raw, file.filename, "application/pdf", {"type":"pdf","owner_type":"course_source_pdf","course_id":"pending"})
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    source_pdf_url=f"/api/v1/media/{media_id}"
    course_id=uuid.uuid4().hex
    course_title=(title or generated.get("title") or file.filename).strip()
    course={"_id":course_id,"name":course_title,"title":course_title,"description":f"Course generated from {file.filename}. The PDF structure is used as the source of truth; no lesson content is invented.","short_description":f"Imported from {file.filename}"[:180],"category":category,"subcategory":"","level":level,"language":language,"is_free":True,"featured":False,"is_published":False,"learning_objectives":[],"prerequisites":[],"estimated_minutes":0,"instructor_name":"Smart Learning Lab","exam":"General","tags":[category.lower()],"rating":0,"students_count":0,"video_count":0,"pdf_count":1,"mock_test_count":0,"source_pdf_name":file.filename,"source_pdf_size":len(raw),"source_pdf_media_id":str(media_id),"source_pdf_storage_key":storage_key,"source_pdf_url":source_pdf_url,"source_pdf_page_count":generated.get("page_count",0),"pdf_import_strategy":generated.get("strategy"),"pdf_import_report":{"toc_pages":generated.get("toc_pages",[]),"source_topic_count":generated.get("source_topic_count",0),"missing_topics":generated.get("missing_topics",0),"lessons_with_content":generated.get("lessons_with_content",0)},"bulk_imported":True,"created_at":now(),"updated_at":now(),"created_by":uid(user)}
    db.courses.insert_one(course)
    db.course_resources.insert_one({"_id":uuid.uuid4().hex,"course_id":course_id,"title":file.filename,"description":"Original PDF used to generate this course.","url":source_pdf_url,"media_id":str(media_id),"storage":"r2","storage_key":storage_key,"filename":file.filename,"content_type":"application/pdf","type":"pdf","source":"bulk_course_pdf_v2","order":1,"created_at":now(),"created_by":uid(user)})

    module_count=lesson_count=0
    for mi,module in enumerate(modules,1):
        mid=uuid.uuid4().hex
        db.topics.insert_one({"_id":mid,"course_id":course_id,"name":module.get("title") or f"Module {mi}","title":module.get("title") or f"Module {mi}","description":module.get("description","") or "Source section from the uploaded PDF.","order":mi,"is_published":False,"created_at":now(),"created_by":uid(user)})
        module_count+=1
        for li,lesson in enumerate(module.get("lessons",[]),1):
            content=lesson.get("content","")
            lid=uuid.uuid4().hex
            db.lessons.insert_one({"_id":lid,"course_id":course_id,"topic_id":mid,"title":lesson.get("title") or f"Lesson {li}","name":lesson.get("title") or f"Lesson {li}","description":f"Source content from the uploaded PDF.","content":content,"content_blocks":lesson.get("content_blocks",[]),"duration_minutes":max(5,min(180,5+len(content.split())//120)),"order":li,"resources":[],"content_source":lesson.get("content_source","pdf"),"source_topic_number":lesson.get("source_number"),"source_group":module.get("title","Course Content"),"source_pages":lesson.get("source_pages",[]),"source_page_start":lesson.get("source_page_start"),"source_page_end":lesson.get("source_page_end"),"source_pdf_url":source_pdf_url,"is_published":False,"created_at":now(),"created_by":uid(user)})
            lesson_count+=1
    db.courses.update_one({"_id":course_id},{"$set":{"estimated_minutes":sum(int(l.get("duration_minutes",20) or 20) for m in modules for l in m.get("lessons",[]))}})
    return {"course_id":course_id,"course":clean(db.courses.find_one({"_id":course_id})),"module_count":module_count,"lesson_count":lesson_count,"source_pages_text_length":generated.get("text_length",0),"source_topic_count":generated.get("source_topic_count",0),"source_topics_with_content":generated.get("lessons_with_content",lesson_count),"missing_topics":generated.get("missing_topics",0),"generation":generated.get("strategy","generic-pdf"),"message":f"Course draft created using {generated.get('strategy','generic-pdf')}. {lesson_count} lessons contain source PDF content. Missing TOC items are not invented or turned into blank lessons."}
