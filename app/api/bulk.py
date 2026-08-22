from datetime import datetime, timezone
import io, uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.core.security import admin_user
from app.db.mongo import get_db
from app.api.media import COURSE_CATEGORIES
from gridfs import GridFSBucket
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

@router.post("/quiz")
def bulk_quiz(data: dict, user=Depends(admin_user)):
    if not isinstance(data, dict):
        raise HTTPException(422, "Request body must be a JSON object")

    db = get_db()
    questions = validate_questions(data.get("questions"))
    title = str(data.get("title", "")).strip()
    if not title:
        raise HTTPException(422, "Quiz title is required")
    if len(title) > 200:
        raise HTTPException(422, "Quiz title must be 200 characters or fewer")

    try:
        duration = int(data.get("duration_minutes", max(15, len(questions) * 2)) or 15)
        passing = int(data.get("passing_percentage", 60) or 60)
        max_attempts = int(data.get("max_attempts", 3) or 3)
    except (TypeError, ValueError):
        raise HTTPException(422, "duration_minutes, passing_percentage and max_attempts must be numbers")

    if duration < 1 or duration > 600:
        raise HTTPException(422, "duration_minutes must be between 1 and 600")
    if passing < 0 or passing > 100:
        raise HTTPException(422, "passing_percentage must be between 0 and 100")
    if max_attempts < 1 or max_attempts > 100:
        raise HTTPException(422, "max_attempts must be between 1 and 100")

    qids=[]
    for q in questions:
        q["created_at"]=now(); q["created_by"]=uid(user); db.questions.insert_one(q); qids.append(q["_id"])
    quiz_id=uuid.uuid4().hex
    quiz={"_id":quiz_id,"title":title,"name":title,"description":str(data.get("description","")),"course_id":data.get("course_id"),"module_id":data.get("module_id"),"duration_minutes":duration,"passing_percentage":passing,"max_attempts":max_attempts,"question_ids":qids,"category":require_quiz_category(data.get("category","General")),"is_published":False,"created_at":now(),"updated_at":now(),"created_by":uid(user),"bulk_imported":True}
    db.quizzes.insert_one(quiz)
    return {"quiz":clean(quiz),"question_count":len(qids),"message":"Bulk quiz saved as draft. Review and publish it from Test Series."}

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

    db=get_db(); bucket=GridFSBucket(db,bucket_name="sll_media")
    media_id=bucket.upload_from_stream(file.filename,io.BytesIO(raw),metadata={"content_type":"application/pdf","resource_type":"pdf","owner_type":"course_source_pdf","uploaded_by":uid(user),"source":"bulk_course_pdf_v2","uploaded_at":now()})
    source_pdf_url=f"/api/v1/media/{media_id}"
    course_id=uuid.uuid4().hex
    course_title=(title or generated.get("title") or file.filename).strip()
    course={"_id":course_id,"name":course_title,"title":course_title,"description":f"Course generated from {file.filename}. The PDF structure is used as the source of truth; no lesson content is invented.","short_description":f"Imported from {file.filename}"[:180],"category":category,"subcategory":"","level":level,"language":language,"is_free":True,"featured":False,"is_published":False,"learning_objectives":[],"prerequisites":[],"estimated_minutes":0,"instructor_name":"Smart Learning Lab","exam":"General","tags":[category.lower()],"rating":0,"students_count":0,"video_count":0,"pdf_count":1,"mock_test_count":0,"source_pdf_name":file.filename,"source_pdf_size":len(raw),"source_pdf_media_id":str(media_id),"source_pdf_url":source_pdf_url,"source_pdf_page_count":generated.get("page_count",0),"pdf_import_strategy":generated.get("strategy"),"pdf_import_report":{"toc_pages":generated.get("toc_pages",[]),"source_topic_count":generated.get("source_topic_count",0),"missing_topics":generated.get("missing_topics",0),"lessons_with_content":generated.get("lessons_with_content",0)},"bulk_imported":True,"created_at":now(),"updated_at":now(),"created_by":uid(user)}
    db.courses.insert_one(course)
    db.course_resources.insert_one({"_id":uuid.uuid4().hex,"course_id":course_id,"title":file.filename,"description":"Original PDF used to generate this course.","url":source_pdf_url,"media_id":str(media_id),"filename":file.filename,"content_type":"application/pdf","type":"pdf","source":"bulk_course_pdf_v2","order":1,"created_at":now(),"created_by":uid(user)})

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
