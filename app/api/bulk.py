from datetime import datetime, timezone
import io, uuid, json
from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File, Form
from app.core.security import admin_user
from app.db.mongo import get_db
from app.api.media import COURSE_CATEGORIES, upload_bytes
from app.services.pdf_course_importer import build_course_from_pdf
from app.services.taxonomy import resolve_links

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


def _form_list(value):
    """Accept JSON-array and comma-separated multipart values."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return [x.strip() for x in text.split(",") if x.strip()]


def resolve_upload_links(payload=None, *, category_ids=None, categories=None, subcategory_ids=None, subcategories=None):
    """Resolve taxonomy once for an entire bulk upload.

    Category/subcategory are upload-level metadata selected by the admin UI.
    They are intentionally not read from individual quiz documents.
    """
    if payload is not None and isinstance(payload, dict):
        category_ids = payload.get("category_ids", category_ids)
        categories = payload.get("categories", categories)
        subcategory_ids = payload.get("subcategory_ids", subcategory_ids)
        subcategories = payload.get("subcategories", subcategories)

    category_ids = _form_list(category_ids)
    categories = _form_list(categories)
    subcategory_ids = _form_list(subcategory_ids)
    subcategories = _form_list(subcategories)

    if not category_ids and not categories:
        raise HTTPException(422, "Select at least one category in the admin UI before uploading.")
    if not subcategory_ids and not subcategories:
        raise HTTPException(422, "Select at least one subcategory in the admin UI before uploading.")

    return resolve_links(category_ids, categories, subcategory_ids, subcategories)


def _i18n_text(value, language="english"):
    """Return a language-specific string from a plain string or i18n object."""
    if isinstance(value, dict):
        keys = ("english", "en") if language == "english" else ("hindi", "hi")
        for key in keys:
            if value.get(key) is not None:
                return str(value[key]).strip()
        # Graceful fallback when only the other language is supplied.
        for key in ("english", "en", "hindi", "hi"):
            if value.get(key) is not None:
                return str(value[key]).strip()
        return ""
    return str(value or "").strip()


def _normalize_bulk_options(q):
    """Normalize all supported single-language/bilingual option schemas."""
    options = q.get("options")
    english = []
    hindi = []
    bilingual = False

    if isinstance(options, dict):
        english = options.get("english") or options.get("en") or []
        hindi = options.get("hindi") or options.get("hi") or []
        bilingual = any(key in options for key in ("english", "en", "hindi", "hi"))
    elif isinstance(options, list):
        english = options

    if isinstance(q.get("options_hindi"), list):
        hindi = q["options_hindi"]
        bilingual = True

    paired = q.get("options_bilingual")
    if isinstance(paired, list) and paired:
        english = [_i18n_text(x, "english") for x in paired]
        hindi = [_i18n_text(x, "hindi") for x in paired]
        bilingual = True

    english = list(english or [])
    hindi = list(hindi or [])

    # A single-language upload remains valid. For consistent student rendering,
    # mirror the available language into the missing language.
    if not english and hindi:
        english = list(hindi)
    if not hindi and english:
        hindi = list(english)

    return [str(x).strip() for x in english], [str(x).strip() for x in hindi], bilingual


def _resolve_bulk_answer(value, english_options, hindi_options):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value

    text = str(value or "").strip()
    if len(text) == 1 and text.upper() in "ABCD":
        return ord(text.upper()) - ord("A")

    try:
        return int(text)
    except (TypeError, ValueError):
        pass

    lowered = text.casefold()
    for index, option in enumerate(english_options):
        if option.casefold() == lowered:
            return index
    for index, option in enumerate(hindi_options):
        if option.casefold() == lowered:
            return index
    return -1


def validate_questions(questions):
    """Validate and normalize single-language or bilingual MCQ questions.

    Accepted formats:
      - question: string; options: ["A", "B", "C", "D"]
      - question: {english: "...", hindi: "..."}
        options: {english: [...], hindi: [...]}
      - question_hindi + options_hindi legacy fields
      - options_bilingual: [{english: "...", hindi: "..."}]
    """
    if not isinstance(questions, list) or not questions:
        raise HTTPException(422, "At least one question is required")

    out = []
    seen_questions = set()

    for i, q in enumerate(questions, 1):
        if not isinstance(q, dict):
            raise HTTPException(422, f"Question {i} must be a JSON object")

        english_question = _i18n_text(q.get("question"), "english")
        hindi_question = _i18n_text(q.get("question"), "hindi")
        if q.get("question_hindi") is not None:
            hindi_question = _i18n_text(q.get("question_hindi"), "hindi") or hindi_question

        if not english_question and not hindi_question:
            raise HTTPException(422, f"Question {i}: question text is empty")

        english_options, hindi_options, options_bilingual = _normalize_bulk_options(q)
        question_bilingual = isinstance(q.get("question"), dict) or q.get("question_hindi") is not None
        bilingual = question_bilingual or options_bilingual
        if len(english_options) != 4:
            raise HTTPException(422, f"Question {i}: exactly four English options are required")
        if bilingual and len(hindi_options) != 4:
            raise HTTPException(422, f"Question {i}: exactly four Hindi options are required for bilingual content")

        if not bilingual and not hindi_options:
            hindi_options = list(english_options)
        if any(not x for x in english_options + hindi_options):
            raise HTTPException(422, f"Question {i}: options cannot be empty")

        def has_duplicates(values):
            normalized = [" ".join(x.casefold().split()) for x in values]
            return len(normalized) != len(set(normalized))

        if has_duplicates(english_options):
            raise HTTPException(422, f"Question {i}: duplicate English options are not allowed")
        if has_duplicates(hindi_options):
            raise HTTPException(422, f"Question {i}: duplicate Hindi options are not allowed")

        correct = _resolve_bulk_answer(
            q.get("correct_answer", q.get("answer", 0)),
            english_options,
            hindi_options,
        )
        if correct not in range(4):
            raise HTTPException(422, f"Question {i}: correct_answer must be 0, 1, 2, 3, A, B, C or D")

        question_key = " ".join((english_question or hindi_question).casefold().split())
        if question_key in seen_questions:
            raise HTTPException(422, f"Question {i}: duplicate question is not allowed")
        seen_questions.add(question_key)

        explanation = q.get("explanation", "")
        explanation_english = _i18n_text(explanation, "english")
        explanation_hindi = _i18n_text(explanation, "hindi")
        if q.get("explanation_hindi") is not None:
            explanation_hindi = _i18n_text(q.get("explanation_hindi"), "hindi") or explanation_hindi

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
            "question": english_question or hindi_question,
            "question_hindi": hindi_question or english_question,
            "question_i18n": {
                "english": english_question or hindi_question,
                "hindi": hindi_question or english_question,
            },
            "question_type": str(q.get("question_type", "mcq")),
            "options": english_options,
            "options_hindi": hindi_options,
            "options_bilingual": [
                {"english": english_options[index], "hindi": hindi_options[index]}
                for index in range(4)
            ],
            "correct_answer": correct,
            "answer": correct,
            "difficulty": difficulty,
            "marks": max(1, marks),
            "negative_marks": max(0, negative_marks),
            "explanation": explanation_english or explanation_hindi,
            "explanation_hindi": explanation_hindi or explanation_english,
            "explanation_i18n": {
                "english": explanation_english or explanation_hindi,
                "hindi": explanation_hindi or explanation_english,
            },
            "tags": tags,
            "is_published": False,
        })

    return out

def normalize_quiz_documents(payload, upload_links=None):
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

    if upload_links is None:
        upload_links = resolve_upload_links(payload)

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

        subject = str(document.get("subject") or "").strip() or "Other"

        # Taxonomy is upload-level metadata. Every quiz in this request receives
        # exactly the same category/subcategory selection from the admin UI.
        links = upload_links

        normalized.append({
            "source_index": index,
            "title": title,
            "description": str(document.get("description", "")).strip(),
            "subject": subject,
            **links,
            "category": links["categories"][0],
            "subcategory": links["subcategories"][0],
            "course_id": document.get("course_id"),
            "module_id": document.get("module_id"),
            "topic": topic,
            "duration_minutes": duration,
            "passing_percentage": passing,
            "max_attempts": max_attempts,
            "questions": questions,
        })

    return normalized


def _quiz_documents_from_payload(payload):
    """Extract quiz documents without applying the 500-item legacy limit."""
    if isinstance(payload, dict) and isinstance(payload.get("quizzes"), list):
        return payload["quizzes"]
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]
    raise HTTPException(422, "Quiz JSON must be one quiz object, an array of quiz objects, or an object containing a 'quizzes' array")


def _insert_quiz_document(document, user, db, *, bulk_upload_id=None, source_index=None):
    """Insert one already-normalized quiz and its questions safely."""
    qids = []
    quiz_id = uuid.uuid4().hex
    quiz = {
        "_id": quiz_id,
        "title": document["title"],
        "name": document["title"],
        "description": document["description"],
        "course_id": document["course_id"],
        "module_id": document["module_id"],
        "topic": document["topic"],
        "subject": document["subject"],
        "category_ids": document["category_ids"],
        "categories": document["categories"],
        "subcategory_ids": document["subcategory_ids"],
        "subcategories": document["subcategories"],
        "category": document["category"],
        "subcategory": document["subcategory"],
        "quiz_group_key": (document["subject"] + "|" + document["title"]).casefold().strip(),
        "duration_minutes": document["duration_minutes"],
        "passing_percentage": document["passing_percentage"],
        "max_attempts": document["max_attempts"],
        "question_ids": [],
        "is_published": False,
        "created_at": now(),
        "updated_at": now(),
        "created_by": uid(user),
        "bulk_imported": True,
    }
    if bulk_upload_id:
        quiz["bulk_upload_id"] = str(bulk_upload_id)
        quiz["bulk_source_index"] = int(source_index or document.get("source_index") or 0)

    db.quizzes.insert_one(quiz)
    try:
        for question in document["questions"]:
            question["created_at"] = now()
            question["created_by"] = uid(user)
            db.questions.insert_one(question)
            qids.append(question["_id"])
        db.quizzes.update_one({"_id": quiz_id}, {"$set": {"question_ids": qids, "updated_at": now()}})
        quiz["question_ids"] = qids
    except Exception:
        if qids:
            db.questions.delete_many({"_id": {"$in": qids}})
        db.quizzes.delete_one({"_id": quiz_id})
        raise

    return quiz, len(qids)


def create_quiz_batch(payload, user, upload_links=None, *, bulk_upload_id=None):
    """Process at most 50 quizzes and return per-quiz results.

    This endpoint is deliberately batch-sized so the frontend can process files
    containing hundreds or thousands of quizzes without sending a huge request.
    A bulk upload id/source index makes a retried batch idempotent.
    """
    documents = _quiz_documents_from_payload(payload)
    if not documents:
        raise HTTPException(422, "At least one quiz is required")
    if len(documents) > 50:
        raise HTTPException(413, "A quiz batch can contain at most 50 quizzes")

    if upload_links is None:
        upload_links = resolve_upload_links(payload)

    db = get_db()
    created = []
    skipped = []
    failed = []
    seen_titles = set()

    for local_index, raw in enumerate(documents, 1):
        source_index = raw.get("_bulk_source_index", local_index) if isinstance(raw, dict) else local_index
        title_hint = str(raw.get("title", raw.get("name", ""))).strip() if isinstance(raw, dict) else ""
        try:
            if not isinstance(raw, dict):
                raise HTTPException(422, f"Quiz {local_index} must be a JSON object")

            title_key = title_hint.casefold()
            if title_key and title_key in seen_titles:
                raise HTTPException(422, f"Quiz {local_index}: duplicate quiz title '{title_hint}' in this batch")
            if title_key:
                seen_titles.add(title_key)

            if bulk_upload_id:
                existing = db.quizzes.find_one({
                    "bulk_upload_id": str(bulk_upload_id),
                    "bulk_source_index": int(source_index),
                })
                if existing:
                    skipped.append({
                        "source_index": int(source_index),
                        "title": existing.get("title") or title_hint,
                        "reason": "Already processed in this bulk upload.",
                        "quiz_id": str(existing.get("_id")),
                    })
                    continue

            # Add the original absolute index so a retry of batch N cannot
            # accidentally create the same quiz twice.
            raw_with_index = dict(raw)
            raw_with_index["_bulk_source_index"] = int(source_index)
            normalized = normalize_quiz_documents([raw_with_index], upload_links=upload_links)[0]

            # Protect against duplicates even when the same JSON is uploaded
            # again with a new bulk_upload_id.
            existing_by_identity = db.quizzes.find_one({
                "title": normalized["title"],
                "subject": normalized["subject"],
                "topic": normalized["topic"],
            })
            if existing_by_identity:
                skipped.append({
                    "source_index": int(source_index),
                    "title": normalized["title"],
                    "reason": "Quiz already exists with the same title, subject and topic.",
                    "quiz_id": str(existing_by_identity.get("_id")),
                })
                continue

            quiz, question_count = _insert_quiz_document(
                normalized, user, db, bulk_upload_id=bulk_upload_id, source_index=source_index
            )
            created.append({
                "quiz": clean(quiz),
                "question_count": question_count,
                "source_index": int(source_index),
                "topic": normalized["topic"],
            })
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            failed.append({"source_index": int(source_index), "title": title_hint, "error": detail})
        except Exception as exc:
            logger = __import__("logging").getLogger("smart_learning_lab.api.bulk")
            logger.exception("BULK_QUIZ_ITEM_FAILED | source_index=%s | title=%s", source_index, title_hint)
            failed.append({"source_index": int(source_index), "title": title_hint, "error": "Unexpected database error while creating this quiz."})

    total_questions = sum(x["question_count"] for x in created)
    return {
        "status": "completed",
        "batch_size": len(documents),
        "created_count": len(created),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "created_quizzes": created,
        "skipped_quizzes": skipped,
        "failed_quizzes": failed,
        "quiz_count": len(created),
        "question_count": total_questions,
        "message": f"Batch completed: {len(created)} created, {len(skipped)} skipped, {len(failed)} failed.",
    }


def create_quiz_drafts(payload, user, upload_links=None):
    """Legacy bulk endpoint. It remains compatible and supports up to 500 quizzes."""
    documents = normalize_quiz_documents(payload, upload_links=upload_links)
    db = get_db()
    created = []
    for document in documents:
        quiz, question_count = _insert_quiz_document(document, user, db)
        created.append({
            "quiz": clean(quiz),
            "question_count": question_count,
            "source_index": document["source_index"],
            "topic": document["topic"],
        })

    total_questions = sum(x["question_count"] for x in created)
    return {
        "quizzes": [x["quiz"] for x in created],
        "created_quizzes": created,
        "quiz_count": len(created),
        "question_count": total_questions,
        "total_question_count": total_questions,
        "message": f"{len(created)} quiz draft(s) created. Review them in Test Series before publishing.",
    }


@router.post("/quiz")
def bulk_quiz(data: object = Body(...), user=Depends(admin_user)):
    # The FE sends taxonomy once at the upload level and the backend applies it
    # to every quiz in the request. Individual quiz category fields are ignored.
    return create_quiz_drafts(data, user)


@router.post("/quiz-batch")
def bulk_quiz_batch(data: object = Body(...), user=Depends(admin_user)):
    """Create one frontend batch of at most 50 quizzes.

    The frontend is responsible for splitting a large JSON file into 50-item
    batches. This endpoint returns per-item failures instead of failing the
    whole batch, so one malformed quiz cannot stop the remaining 49.
    """
    if not isinstance(data, dict):
        raise HTTPException(422, "Batch payload must be a JSON object")
    upload_links = resolve_upload_links(data)
    bulk_upload_id = data.get("bulk_upload_id")
    quizzes = data.get("quizzes")
    if not isinstance(quizzes, list):
        raise HTTPException(422, "Batch payload must contain a 'quizzes' array")
    return create_quiz_batch(quizzes, user, upload_links=upload_links, bulk_upload_id=bulk_upload_id)


@router.post("/quiz-file")
async def bulk_quiz_file(
    file: UploadFile = File(...),
    categories: str = Form(""),
    subcategories: str = Form(""),
    category_ids: str = Form(""),
    subcategory_ids: str = Form(""),
    user=Depends(admin_user),
):
    if not file.filename:
        raise HTTPException(422, "JSON file is required")
    if not file.filename.lower().endswith((".json", ".txt")):
        raise HTTPException(422, "Upload a .json file (a .txt file containing valid JSON is also supported)")

    upload_links = resolve_upload_links(
        category_ids=category_ids,
        categories=categories,
        subcategory_ids=subcategory_ids,
        subcategories=subcategories,
    )

    raw = await file.read()
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(413, "Quiz JSON file is too large. Maximum supported size is 20 MB.")

    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, f"Invalid JSON file: {exc}")

    return create_quiz_drafts(payload, user, upload_links=upload_links)


@router.post("/course-pdf")
async def bulk_course_pdf(file:UploadFile=File(...),title:str=Form(""),subject:str=Form("Other"),categories:str=Form(""),category:str=Form(""),subcategories:str=Form(""),subcategory:str=Form(""),category_ids:str=Form(""),subcategory_ids:str=Form(""),level:str=Form("Beginner"),language:str=Form("English"),user=Depends(admin_user)):
    if not file.filename: raise HTTPException(422,"PDF file is required")
    if not file.filename.lower().endswith(".pdf"): raise HTTPException(422,"Only PDF files are supported")
    subject = str(subject or "Other").strip() or "Other"
    links = resolve_links(category_ids, categories or category, subcategory_ids, subcategories or subcategory)
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
    course={"_id":course_id,"name":course_title,"title":course_title,"description":f"Course generated from {file.filename}. The PDF structure is used as the source of truth; no lesson content is invented.","short_description":f"Imported from {file.filename}"[:180],"subject":subject,"category_ids":links["category_ids"],"categories":links["categories"],"subcategory_ids":links["subcategory_ids"],"subcategories":links["subcategories"],"category":links["categories"][0],"subcategory":links["subcategories"][0],"level":level,"language":language,"is_free":True,"featured":False,"is_published":False,"learning_objectives":[],"prerequisites":[],"estimated_minutes":0,"instructor_name":"Smart Learning Lab","exam":"General","tags":[x.lower() for x in links["categories"] + links["subcategories"]],"rating":0,"students_count":0,"video_count":0,"pdf_count":1,"mock_test_count":0,"source_pdf_name":file.filename,"source_pdf_size":len(raw),"source_pdf_media_id":str(media_id),"source_pdf_storage_key":storage_key,"source_pdf_url":source_pdf_url,"source_pdf_page_count":generated.get("page_count",0),"pdf_import_strategy":generated.get("strategy"),"pdf_import_report":{"toc_pages":generated.get("toc_pages",[]),"source_topic_count":generated.get("source_topic_count",0),"missing_topics":generated.get("missing_topics",0),"lessons_with_content":generated.get("lessons_with_content",0)},"bulk_imported":True,"created_at":now(),"updated_at":now(),"created_by":uid(user)}
    db.courses.insert_one(course)
    db.course_resources.insert_one({"_id":uuid.uuid4().hex,"course_id":course_id,"title":file.filename,"description":"Original PDF used to generate this course.","url":source_pdf_url,"media_id":str(media_id),"storage":"r2","storage_key":storage_key,"filename":file.filename,"content_type":"application/pdf","type":"pdf","source":"bulk_course_pdf_v2","order":1,"created_at":now(),"created_by":uid(user)})

    module_count=lesson_count=0
    for mi,module in enumerate(modules,1):
        mid=uuid.uuid4().hex
        db.topics.insert_one({"_id":mid,"course_id":course_id,"subject":subject,"category_ids":links["category_ids"],"categories":links["categories"],"subcategory_ids":links["subcategory_ids"],"subcategories":links["subcategories"],"name":module.get("title") or f"Module {mi}","title":module.get("title") or f"Module {mi}","description":module.get("description","") or "Source section from the uploaded PDF.","order":mi,"is_published":False,"created_at":now(),"created_by":uid(user)})
        module_count+=1
        for li,lesson in enumerate(module.get("lessons",[]),1):
            content=lesson.get("content","")
            lid=uuid.uuid4().hex
            db.lessons.insert_one({"_id":lid,"course_id":course_id,"topic_id":mid,"title":lesson.get("title") or f"Lesson {li}","name":lesson.get("title") or f"Lesson {li}","description":f"Source content from the uploaded PDF.","content":content,"content_blocks":lesson.get("content_blocks",[]),"duration_minutes":max(5,min(180,5+len(content.split())//120)),"order":li,"resources":[],"content_source":lesson.get("content_source","pdf"),"source_topic_number":lesson.get("source_number"),"source_group":module.get("title","Course Content"),"source_pages":lesson.get("source_pages",[]),"source_page_start":lesson.get("source_page_start"),"source_page_end":lesson.get("source_page_end"),"source_pdf_url":source_pdf_url,"is_published":False,"created_at":now(),"created_by":uid(user)})
            lesson_count+=1
    db.courses.update_one({"_id":course_id},{"$set":{"estimated_minutes":sum(int(l.get("duration_minutes",20) or 20) for m in modules for l in m.get("lessons",[]))}})
    return {"course_id":course_id,"course":clean(db.courses.find_one({"_id":course_id})),"module_count":module_count,"lesson_count":lesson_count,"source_pages_text_length":generated.get("text_length",0),"source_topic_count":generated.get("source_topic_count",0),"source_topics_with_content":generated.get("lessons_with_content",lesson_count),"missing_topics":generated.get("missing_topics",0),"generation":generated.get("strategy","generic-pdf"),"message":f"Course draft created using {generated.get('strategy','generic-pdf')}. {lesson_count} lessons contain source PDF content. Missing TOC items are not invented or turned into blank lessons."}
