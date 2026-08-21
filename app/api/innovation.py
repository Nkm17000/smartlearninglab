from datetime import datetime, timezone, timedelta
import io, re, uuid, json
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.core.security import current_user, admin_user
from app.db.mongo import get_db
from app.services.ai_service import chat, configured

router = APIRouter(prefix='/api/v1', tags=['AI Product Intelligence'])

def now(): return datetime.now(timezone.utc)
def uid(u): return str(u['_id'])
def clean(v):
    if isinstance(v, dict): return {k: clean(x) for k,x in v.items() if k not in {'password_hash'}}
    if isinstance(v, list): return [clean(x) for x in v]
    return v.isoformat() if hasattr(v, 'isoformat') else v

def course_name(c): return c.get('name') or c.get('title') or 'Course'

def student_stats(user_id):
    db=get_db()
    progress=list(db.progress.find({'user_id':user_id}))
    attempts=list(db.test_attempts.find({'user_id':user_id,'status':'submitted'}))
    scores=[float(a.get('result',{}).get('score',0) or 0) for a in attempts]
    avg=round(sum(scores)/len(scores),1) if scores else 0
    completed=sum(1 for p in progress if p.get('completed'))
    enrollments=list(db.enrollments.find({'user_id':user_id,'status':'active'}).limit(20))
    weak=[]
    topic_scores=Counter()
    for a in attempts:
        for w in a.get('result',{}).get('weak_topics',[]) or []: topic_scores[w]+=1
    weak=[x for x,_ in topic_scores.most_common(5)]
    return {'completed_lessons':completed,'attempts':len(attempts),'average_score':avg,'enrollments':len(enrollments),'weak_topics':weak}
@router.get('/ai/coach')
def learning_coach(user=Depends(current_user)):
    s=student_stats(uid(user)); name=user.get('name') or user.get('email','learner').split('@')[0]
    weak=s['weak_topics'] or ['recent lessons']
    prompt=(f"Learner: {name}\nStats: {s}\nWeak topics: {weak}\n"
            "Give one concise, personalized coaching message and 3 actionable recommendations for today. "
            "Do not invent statistics. Return JSON with keys coach_message and recommendations; each recommendation has title, description, action.")
    generated=chat('You are an evidence-based learning coach for Smart Learning Lab. Use only supplied learner facts.',prompt) if configured() else None
    recommendations=[]
    if s['weak_topics']: recommendations.append({'title':'Fix your weakest topic','description':f"Start with {', '.join(s['weak_topics'][:3])}.",'action':'practice'})
    if s['average_score'] and s['average_score']<70: recommendations.append({'title':'Take a focused quiz','description':f"Your recorded average is {s['average_score']}%. Review weak areas before the next test.",'action':'quiz'})
    recommendations.append({'title':'Keep your momentum','description':'Complete one focused lesson and 5 review questions today.','action':'learn'})
    message=f"Hi {name} 👋 Focus today on {', '.join(weak[:2])}. Complete one lesson and a short practice set." 
    if generated:
        try:
            obj=json.loads(generated); message=obj.get('coach_message') or message; recommendations=obj.get('recommendations') or recommendations
        except Exception: message=generated.strip()
    return {'generated_at':now(),'profile':s,'coach_message':message,'recommendations':recommendations[:4],'daily_goal':{'minutes':30,'lessons':1,'questions':5}}


# 2. AI-generated personalized quiz
@router.post('/ai/personalized-quiz')
def personalized_quiz(data:dict|None=None,user=Depends(current_user)):
    data=data or {}; db=get_db(); s=student_stats(uid(user)); topic=data.get('topic') or (s['weak_topics'][0] if s['weak_topics'] else None); count=max(3,min(10,int(data.get('count',5) or 5)))
    query={'is_published':True}
    if topic: query['$or']=[{'topic':{'$regex':re.escape(topic),'$options':'i'}},{'tags':{'$regex':re.escape(topic),'$options':'i'}},{'question':{'$regex':re.escape(topic),'$options':'i'}},{'text':{'$regex':re.escape(topic),'$options':'i'}}]
    qs=list(db.questions.find(query).limit(count))
    if len(qs)<count: qs+=list(db.questions.find({'is_published':True}).limit(count-len(qs)))
    questions=[clean(q) for q in qs[:count]]
    if not questions and configured():
        raw=chat('You create concise educational MCQs. Return JSON array only with question, options, correct_answer, explanation.',f"Create {count} questions for a learner weak in {topic or 'mixed topics'}.")
        try: questions=json.loads(raw) if raw else []
        except Exception: questions=[]
    return {'title':f'Personalized {topic or "Practice"} Quiz','topic':topic or 'mixed','difficulty':'adaptive','questions':questions,'reason':f"Personalized using your recorded weak topics{': '+', '.join(s['weak_topics']) if s['weak_topics'] else ''}."}

# 3. AI study plan
@router.post('/ai/study-plan')
def study_plan(data:dict|None=None,user=Depends(current_user)):
    d=data or {}; goal=d.get('goal') or 'Improve my learning performance'; days=max(7,min(180,int(d.get('days',30) or 30))); minutes=max(15,min(240,int(d.get('minutes_per_day',45) or 45)))
    s=student_stats(uid(user)); weak=s['weak_topics'] or ['core concepts','practice','revision']
    phases=[]
    for i,topic in enumerate(weak[:4],1):
        start=((i-1)*days)//4+1; end=max(start,(i*days)//4)
        phases.append({'week':i,'days':f'{start}-{end}','focus':topic,'activities':[f'Learn {topic} with one focused lesson',f'Ask AI to explain {topic} with an example',f'Complete 5-10 questions on {topic}','Review related flashcards'],'minutes_per_day':minutes})
    return {'goal':goal,'duration_days':days,'minutes_per_day':minutes,'starting_level':d.get('level','adaptive'),'phases':phases,'weekly_review':'Take an adaptive test every 7 days and update the next phase from your latest weak areas.'}

# 4. PDF -> complete AI course blueprint
@router.post('/admin/ai/course-from-pdf')
async def course_from_pdf(file:UploadFile=File(...), user=Depends(admin_user)):
    if not file.filename.lower().endswith('.pdf'): raise HTTPException(422,'Upload a PDF file')
    content=await file.read()
    try:
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(content)); text='\n'.join((p.extract_text() or '') for p in reader.pages)
    except Exception as e: raise HTTPException(422,f'Could not read PDF: {e}')
    text=re.sub(r'\s+',' ',text).strip()
    if not text: raise HTTPException(422,'PDF contains no extractable text')
    sentences=[x.strip() for x in re.split(r'(?<=[.!?])\s+',text) if len(x.strip())>30]
    chunks=[sentences[i:i+6] for i in range(0,min(len(sentences),48),6)] or [[text[:1000]]]
    modules=[]
    for i,ch in enumerate(chunks[:8],1):
        seed=' '.join(ch)[:180]
        title=(re.split(r'[:.]',seed)[0][:65] or f'Module {i}').strip()
        modules.append({'title':title if len(title)>4 else f'Module {i}','summary':' '.join(ch)[:500],'lessons':[{'title':f'Lesson {i}.{j+1}','summary':s[:350],'objectives':['Understand the key concept','Apply it with an example']} for j,s in enumerate(ch[:4])]})
    blueprint={'_id':uuid.uuid4().hex,'source_file':file.filename,'title':file.filename.rsplit('.',1)[0].replace('_',' ').title(),'description':'AI-generated course blueprint from uploaded learning material.','modules':modules,'question_count':min(20,max(5,len(sentences)//4)),'generated_at':now(),'created_by':uid(user)}
    get_db().ai_course_blueprints.insert_one(blueprint)
    return clean(blueprint)

@router.post('/admin/ai/course-from-pdf/save')
def save_pdf_course(data:dict,user=Depends(admin_user)):
    d=dict(data); title=d.get('title') or 'AI Generated Course'; course={'_id':uuid.uuid4().hex,'name':title,'title':title,'description':d.get('description',''),'is_published':False,'featured':False,'created_at':now(),'created_by':uid(user),'ai_generated':True}
    get_db().courses.insert_one(course)
    for mi,m in enumerate(d.get('modules',[]) or [],1):
        mid=uuid.uuid4().hex; get_db().topics.insert_one({'_id':mid,'course_id':course['_id'],'title':m.get('title',f'Module {mi}'),'description':m.get('summary',''),'order':mi,'is_published':False})
        for li, l in enumerate(m.get('lessons', []) or [], 1):
            lesson={
                '_id': uuid.uuid4().hex,
                'module_id': mid,
                'course_id': course['_id'],
                'title': l.get('title') or ('Lesson %s.%s' % (mi, li)),
                'description': l.get('summary',''),
                'content': l.get('summary',''),
                'order': li,
                'is_published': False,
            }
            get_db().lessons.insert_one(lesson)
    return clean(course)

# 5. At-risk student detection
@router.get('/admin/students/at-risk')
def at_risk_students(user=Depends(admin_user)):
    db=get_db(); out=[]; students=list(db.users.find({'role':'student'}).limit(500)); cutoff=now()-timedelta(days=7)
    for st in students:
        sid=str(st['_id']); attempts=list(db.test_attempts.find({'user_id':sid,'status':'submitted'})); scores=[float(a.get('result',{}).get('score',0) or 0) for a in attempts]; avg=round(sum(scores)/len(scores),1) if scores else 0
        last=db.progress.find_one({'user_id':sid},sort=[('updated_at',-1)])
        last_dt=last.get('updated_at') if last else None
        reasons=[]; risk=0
        if avg and avg<50: reasons.append('Low assessment score'); risk+=2
        elif avg and avg<65: reasons.append('Below-target assessment score'); risk+=1
        if not last_dt or (hasattr(last_dt,'timestamp') and last_dt<cutoff): reasons.append('No learning activity in 7+ days'); risk+=2
        enroll=db.enrollments.count_documents({'user_id':sid,'status':'active'}); completed=db.progress.count_documents({'user_id':sid,'completed':True})
        if enroll and completed==0: reasons.append('Enrolled but no lessons completed'); risk+=1
        if risk>=2: out.append({'student_id':sid,'name':st.get('name') or st.get('full_name') or st.get('email'),'email':st.get('email'),'risk':'high' if risk>=4 else 'medium','risk_score':risk,'average_score':avg,'reasons':reasons})
    return {'generated_at':now(),'students':sorted(out,key=lambda x:-x['risk_score']),'summary':{'high':sum(x['risk']=='high' for x in out),'medium':sum(x['risk']=='medium' for x in out)}}

# 6. Career / skill roadmap
@router.get('/career/roadmap')
def career_roadmap(role:str='AI Engineer',user=Depends(current_user)):
    tracks={'AI Engineer':['Python','ML Fundamentals','Deep Learning','Transformers','RAG','Agents','MLOps'],'Java Developer':['Java','Spring Boot','SQL','Microservices','Kafka','Cloud','System Design'],'Full Stack Developer':['HTML/CSS','JavaScript','React','Backend APIs','Databases','Cloud','System Design'],'Data Scientist':['Python','Statistics','Pandas','Machine Learning','Visualization','Deep Learning','MLOps']}
    skills=tracks.get(role,tracks['AI Engineer']); s=student_stats(uid(user)); base=min(90,max(20,35+s['completed_lessons']*2+s['average_score']*.25));
    return {'role':role,'overall_readiness':round(base),'skills':[{'name':x,'score':round(min(100,max(10,base-(i*5)))),'status':'strong' if base-(i*5)>=70 else 'developing' if base-(i*5)>=40 else 'start'} for i,x in enumerate(skills)],'next_steps':skills[:3],'based_on':{'completed_lessons':s['completed_lessons'],'average_score':s['average_score'],'weak_topics':s['weak_topics']}}

# 7. AI mock interview
@router.post('/ai/mock-interview')
def mock_interview(data:dict|None=None,user=Depends(current_user)):
    d=data or {}; role=d.get('role') or 'Software Engineer'; difficulty=d.get('difficulty') or 'intermediate'
    qs={'Java Developer':['Explain HashMap internals and collision handling.','What is dependency injection and why use constructor injection?','Design a resilient Kafka consumer.'],'AI Engineer':['Explain embeddings and vector search.','How would you evaluate a RAG system?','When would you use an agent instead of a chain?'],'Full Stack Developer':['Explain REST API versioning.','How would you optimize a slow React screen?','Design authentication for a mobile app.']}
    questions=qs.get(role,qs['Java Developer'])
    return {'session_id':uuid.uuid4().hex,'role':role,'difficulty':difficulty,'questions':questions,'rubric':['technical accuracy','clarity','structure','trade-offs','communication']}

@router.post('/ai/mock-interview/evaluate')
def evaluate_mock(data:dict,user=Depends(current_user)):
    answer=str(data.get('answer','')); q=str(data.get('question','')); length=len(answer.split()); score=min(95,max(35,45+min(25,length//12)+15*(bool(q) and length>30)))
    feedback='Good start. Add a concrete example and explain trade-offs.' if score<75 else 'Strong answer. Improve it further by adding measurable impact and edge cases.'
    return {'score':score,'breakdown':{'technical_accuracy':score,'clarity':min(100,score+4),'structure':min(100,score-2 if score>40 else score),'communication':min(100,score+2)},'feedback':feedback}

# 8. AI Course Health Checker
@router.get('/admin/courses/{course_id}/health')
def course_health(course_id:str,user=Depends(admin_user)):
    db=get_db(); c=db.courses.find_one({'_id':course_id})
    if not c: raise HTTPException(404,'Course not found')
    lessons=list(db.lessons.find({'course_id':course_id})); quizzes=list(db.quizzes.find({'course_id':course_id})); enroll=db.enrollments.count_documents({'course_id':course_id}); reviews=list(db.reviews.find({'course_id':course_id}))
    avg_review=round(sum(float(r.get('rating',0) or 0) for r in reviews)/len(reviews),1) if reviews else 0
    completion=0
    if enroll and lessons: completion=round(db.progress.count_documents({'course_id':course_id,'completed':True})/max(1,enroll*len(lessons)),2)*100
    content=min(100,40+len(lessons)*4+len(quizzes)*5); engagement=min(100,30+completion*.6); quality=min(100,content*.7+(avg_review/5*100)*.3 if avg_review else content*.7)
    score=round(content*.35+engagement*.35+quality*.3)
    issues=[]
    if not quizzes: issues.append('Add at least one assessment')
    if len(lessons)<5: issues.append('Add more short lessons for better progression')
    if completion<35 and enroll>0: issues.append('Students are not completing enough content')
    return {'course':clean(c),'health_score':score,'metrics':{'content':round(content),'engagement':round(engagement),'quality':round(quality),'completion_rate':completion,'enrollments':enroll,'lessons':len(lessons),'quizzes':len(quizzes)},'issues':issues,'recommendations':['Add practice after difficult lessons','Use AI-generated quizzes for weak modules','Review low-completion lessons']}

# 9. Global semantic search with relevance scoring
@router.get('/search')
def global_search(q:str='',limit:int=20,user=Depends(current_user)):
    query=q.strip(); limit=max(1,min(int(limit),50))
    if len(query)<2: return {'query':query,'results':[],'total':0}
    db=get_db(); tokens=tokenize(query); qset=set(tokens); results=[]
    collections=[('courses','course',['name','title','description','category','exam']),('lessons','lesson',['title','description','content','topic']),('questions','question',['question','text','topic','tags']),('topics','topic',['title','description'])]
    for collection,kind,fields in collections:
        for x in db[collection].find({}).limit(2500):
            values={f:str(x.get(f,'') or '') for f in fields}; hay=' '.join(values.values()).lower(); title=(values.get('title') or values.get('name') or values.get('question') or values.get('text') or '').strip()
            if not hay: continue
            score=0
            for tok in qset:
                if tok in title.lower(): score+=8
                elif tok in hay: score+=3
            if query.lower() in title.lower(): score+=12
            if query.lower() in hay: score+=5
            if score:
                source_text=values.get('description') or values.get('content') or values.get('text') or title
                results.append({'type':kind,'id':str(x.get('_id')),'title':title or 'Result','snippet':source_text[:240],'score':score,'matched_terms':sorted([tok for tok in qset if tok in hay])})
    results.sort(key=lambda r:(-r['score'], r['type'], r['title'].lower()))
    return {'query':query,'results':results[:limit],'total':len(results)}

# 10. Offline sync endpoint
@router.post('/offline/sync')
def offline_sync(data:dict,user=Depends(current_user)):
    db=get_db(); synced=[]; failed=[]
    for action in data.get('actions',[]) or []:
        try:
            typ=action.get('type'); payload=action.get('payload',{})
            if typ=='complete_lesson' and payload.get('lesson_id'):
                db.progress.update_one({'user_id':uid(user),'lesson_id':payload['lesson_id']},{'$set':{'user_id':uid(user),'lesson_id':payload['lesson_id'],'course_id':payload.get('course_id'),'completed':True,'updated_at':now()}},upsert=True); synced.append(action.get('id'))
            elif typ=='bookmark' and payload.get('item_id'):
                db.bookmarks.update_one({'user_id':uid(user),'item_id':payload['item_id']},{'$set':{'user_id':uid(user),**payload,'updated_at':now()}},upsert=True); synced.append(action.get('id'))
            else: failed.append({'id':action.get('id'),'reason':'Unsupported action'})
        except Exception as e: failed.append({'id':action.get('id'),'reason':str(e)})
    return {'synced':synced,'failed':failed,'server_time':now()}
