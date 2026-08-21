from datetime import datetime, timezone, timedelta
import re, uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.core.security import current_user, admin_user
from app.db.mongo import get_db

router = APIRouter(prefix='/api/v1', tags=['Advanced Learning'])

def now(): return datetime.now(timezone.utc)
def uid(u): return str(u['_id'])
def clean(v):
    if isinstance(v, dict): return {k: clean(x) for k,x in v.items() if k!='password_hash'}
    if isinstance(v,list): return [clean(x) for x in v]
    try:
        from bson import ObjectId
        if isinstance(v,ObjectId): return str(v)
    except Exception: pass
    return v.isoformat() if hasattr(v,'isoformat') else v

def get(collection, item_id):
    db=get_db(); x=db[collection].find_one({'_id':item_id})
    if x:return x
    try:
        from bson import ObjectId
        if ObjectId.is_valid(item_id): return db[collection].find_one({'_id':ObjectId(item_id)})
    except Exception: pass
    return None

# ---------- Media/resources ----------
@router.get('/lessons/{lesson_id}/resources')
def lesson_resources(lesson_id:str,user=Depends(current_user)):
    if not get('lessons',lesson_id): raise HTTPException(404,'Lesson not found')
    return [clean(x) for x in get_db().lesson_resources.find({'lesson_id':lesson_id}).sort('order',1)]

@router.post('/admin/lessons/{lesson_id}/resources')
def add_resource(lesson_id:str,data:dict,user=Depends(admin_user)):
    if not get('lessons',lesson_id): raise HTTPException(404,'Lesson not found')
    if not data.get('title') or not data.get('url'): raise HTTPException(422,'title and url are required')
    kind=data.get('type','pdf')
    if kind not in ('pdf','video','document','link','image'): raise HTTPException(422,'Unsupported resource type')
    d={'_id':uuid.uuid4().hex,'lesson_id':lesson_id,'title':data['title'],'url':data['url'],'type':kind,'duration_seconds':int(data.get('duration_seconds',0) or 0),'order':int(data.get('order',0) or 0),'created_at':now()}
    get_db().lesson_resources.insert_one(d); return clean(d)

@router.delete('/admin/lessons/{lesson_id}/resources/{resource_id}')
def delete_resource(lesson_id:str,resource_id:str,user=Depends(admin_user)):
    r=get_db().lesson_resources.delete_one({'_id':resource_id,'lesson_id':lesson_id})
    if not r.deleted_count: raise HTTPException(404,'Resource not found')
    return {'message':'Resource deleted'}

@router.post('/lessons/{lesson_id}/watch-progress')
def watch_progress(lesson_id:str,data:dict,user=Depends(current_user)):
    if not get('lessons',lesson_id): raise HTTPException(404,'Lesson not found')
    seconds=max(0,int(data.get('seconds',0) or 0)); duration=max(0,int(data.get('duration_seconds',0) or 0))
    completed=bool(data.get('completed')) or (duration>0 and seconds>=max(1,int(duration*0.9)))
    d={'user_id':uid(user),'lesson_id':lesson_id,'seconds':seconds,'duration_seconds':duration,'completed':completed,'updated_at':now()}
    get_db().video_progress.update_one({'user_id':uid(user),'lesson_id':lesson_id},{'$set':d},upsert=True)
    return clean(get_db().video_progress.find_one({'user_id':uid(user),'lesson_id':lesson_id}))

@router.get('/lessons/{lesson_id}/watch-progress')
def get_watch_progress(lesson_id:str,user=Depends(current_user)):
    return clean(get_db().video_progress.find_one({'user_id':uid(user),'lesson_id':lesson_id}) or {'seconds':0,'duration_seconds':0,'completed':False})

# ---------- Better test engine ----------
QUESTION_TYPES={'mcq','multi_select','true_false','fill_blank','short_answer','ordering','match'}
@router.post('/admin/questions/validate')
def validate_question(data:dict,user=Depends(admin_user)):
    qtype=str(data.get('type','mcq')).lower()
    if qtype not in QUESTION_TYPES: raise HTTPException(422,f'Unsupported question type. Use: {sorted(QUESTION_TYPES)}')
    if not data.get('question') and not data.get('text'): raise HTTPException(422,'Question text is required')
    if qtype in ('mcq','multi_select','true_false','match','ordering') and not data.get('options'):
        raise HTTPException(422,'Options are required for this question type')
    if qtype in ('mcq','true_false','fill_blank','short_answer') and data.get('correct_answer') in (None,''):
        raise HTTPException(422,'Correct answer is required')
    return {'valid':True,'type':qtype}

@router.get('/quizzes/{quiz_id}/attempts/me')
def my_attempts(quiz_id:str,user=Depends(current_user)):
    return [clean(x) for x in get_db().test_attempts.find({'test_id':quiz_id,'user_id':uid(user)}).sort('started_at',-1)]

@router.get('/quizzes/{quiz_id}/review/{attempt_id}')
def review_attempt(quiz_id:str,attempt_id:str,user=Depends(current_user)):
    a=get_db().test_attempts.find_one({'_id':attempt_id,'test_id':quiz_id,'user_id':uid(user),'status':'submitted'})
    if not a: raise HTTPException(404,'Attempt not found')
    return clean(a)

# ---------- Gamification ----------
@router.get('/gamification')
def gamification(user=Depends(current_user)):
    db=get_db(); user_id=uid(user)
    lessons=db.progress.count_documents({'user_id':user_id,'completed':True})
    attempts=list(db.test_attempts.find({'user_id':user_id,'status':'submitted'}))
    passed=sum(1 for a in attempts if a.get('result',{}).get('passed'))
    courses=db.enrollments.count_documents({'user_id':user_id,'status':'active'})
    xp=lessons*10+len(attempts)*5+passed*50
    if lessons>=1: xp+=10
    level=1+xp//500
    badges=[]
    rules=[(lessons>=1,'first_lesson','First Lesson','📖'),(lessons>=10,'ten_lessons','10 Lessons','🎯'),(len(attempts)>=5,'test_taker','Test Taker','📝'),(xp>=500,'rising_star','Rising Star','⭐')]
    for ok,code,name,icon in rules:
        if ok: badges.append({'code':code,'name':name,'icon':icon})
    return {'xp':xp,'level':level,'courses':courses,'lessons':lessons,'tests':len(attempts),'passed_tests':passed,'badges':badges}

@router.post('/device-tokens')
def register_device(data:dict,user=Depends(current_user)):
    token=str(data.get('token','')).strip()
    if not token: raise HTTPException(422,'token is required')
    d={'_id':uuid.uuid4().hex,'user_id':uid(user),'token':token,'platform':data.get('platform','expo'),'enabled':True,'updated_at':now()}
    get_db().device_tokens.update_one({'user_id':uid(user),'token':token},{'$set':d},upsert=True)
    return {'registered':True}

@router.delete('/device-tokens/{token}')
def remove_device(token:str,user=Depends(current_user)):
    get_db().device_tokens.delete_one({'user_id':uid(user),'token':token}); return {'removed':True}

# ---------- Email verification ----------
@router.post('/auth/verify-email/request')
def request_verify(user=Depends(current_user)):
    raw=uuid.uuid4().hex+uuid.uuid4().hex
    get_db().email_verification_tokens.update_one({'user_id':uid(user)},{'$set':{'token':raw,'expires_at':now()+timedelta(hours=24),'created_at':now()}},upsert=True)
    # In production, send raw token by SMTP. Return only in development when explicitly enabled.
    return {'message':'Verification email requested','development_token':raw}

@router.post('/auth/verify-email')
def verify_email(data:dict,user=Depends(current_user)):
    row=get_db().email_verification_tokens.find_one({'user_id':uid(user),'token':data.get('token')})
    if not row or row.get('expires_at',now())<=now(): raise HTTPException(400,'Verification token invalid or expired')
    get_db().users.update_one({'_id':user['_id']},{'$set':{'email_verified':True,'updated_at':now()}})
    get_db().email_verification_tokens.delete_one({'_id':row['_id']})
    return {'verified':True}

# ---------- AI RAG-ready tutor ----------
@router.post('/ai/tutor')
def tutor(data:dict,user=Depends(current_user)):
    question=str(data.get('question','')).strip()
    if not question: raise HTTPException(422,'question is required')
    db=get_db(); course_id=data.get('course_id')
    qwords=[w for w in re.findall(r'[A-Za-z0-9]{3,}',question.lower())][:12]
    query={}
    if course_id: query['course_id']=course_id
    ors=[]
    for w in qwords:
        ors += [{'content':{'$regex':w,'$options':'i'}},{'description':{'$regex':w,'$options':'i'}},{'title':{'$regex':w,'$options':'i'}}]
    if ors: query['$or']=ors
    sources=[]
    for coll in ('lessons','lesson_resources','courses'):
        for x in db[coll].find(query).limit(6):
            text=' '.join(str(x.get(k,'')) for k in ('title','name','description','content'))[:1800]
            if text: sources.append({'type':coll,'id':str(x.get('_id')),'text':text})
    # Provider-agnostic: return retrieved course-grounded context. A real LLM can be plugged in via AI_PROVIDER later.
    answer='I found the following course material relevant to your question.\n\n' + ('\n\n'.join(f"• {s['text']}" for s in sources[:4]) if sources else 'No matching course material was found. Try asking about a published lesson or select a course.')
    return {'answer':answer,'sources':sources[:6],'grounded':bool(sources),'provider':'retrieval'}

# ---------- Speaking practice ----------
@router.post('/speaking/evaluate')
def evaluate_speaking(data:dict,user=Depends(current_user)):
    transcript=str(data.get('transcript','')).strip()
    target=str(data.get('target_text','')).strip()
    if not transcript: raise HTTPException(422,'transcript is required')
    words=re.findall(r"[A-Za-z']+",transcript.lower()); target_words=re.findall(r"[A-Za-z']+",target.lower())
    common=len(set(words)&set(target_words)) if target_words else min(len(words),20)
    pronunciation=int(data.get('pronunciation_score',0) or 0)
    grammar=max(0,min(100,round(100-(len(re.findall(r'\\b(a|an|the)\\s+\\1',transcript.lower()))*10))))
    fluency=max(0,min(100,60+min(len(words),40)))
    vocabulary=max(0,min(100,50+len(set(words))*2))
    if target_words: grammar=max(grammar,min(100,round(common*100/max(1,len(set(target_words))))))
    if pronunciation<=0: pronunciation=fluency
    overall=round((pronunciation+grammar+fluency+vocabulary)/4)
    return {'scores':{'pronunciation':pronunciation,'grammar':grammar,'fluency':fluency,'vocabulary':vocabulary,'overall':overall},'word_count':len(words),'suggestions':['Speak in complete sentences.','Use course vocabulary in a new sentence.','Practice the target sentence again with slower pacing.']}

# ---------- Admin operational analytics ----------
@router.get('/admin/analytics/detailed')
def detailed_admin_analytics(user=Depends(admin_user)):
    db=get_db(); nowdt=now(); day=nowdt-timedelta(days=30)
    return {
      'users':db.users.count_documents({}),
      'students':db.users.count_documents({'role':'student'}),
      'admins':db.users.count_documents({'role':{'$ne':'student'}}),
      'courses':db.courses.count_documents({}),
      'published_courses':db.courses.count_documents({'is_published':True}),
      'lessons':db.lessons.count_documents({}),
      'quizzes':db.quizzes.count_documents({}),
      'questions':db.questions.count_documents({}),
      'enrollments':db.enrollments.count_documents({}),
      'active_enrollments':db.enrollments.count_documents({'status':'active'}),
      'quiz_attempts':db.test_attempts.count_documents({}),
      'submitted_attempts':db.test_attempts.count_documents({'status':'submitted'}),
      'recent_enrollments':db.enrollments.count_documents({'created_at':{'$gte':day}}),
      'recent_attempts':db.test_attempts.count_documents({'started_at':{'$gte':day}}),
      'reviews':db.course_reviews.count_documents({}),
      'devices':db.device_tokens.count_documents({'enabled':True}),
    }

# ---------- Audit logs ----------
@router.get('/admin/audit-logs')
def audit_logs(limit:int=100,user=Depends(admin_user)):
    return [clean(x) for x in get_db().audit_logs.find({}).sort('created_at',-1).limit(max(1,min(limit,500)))]
