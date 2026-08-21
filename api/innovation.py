from datetime import datetime, timezone, timedelta
import io, re, uuid
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.core.security import current_user, admin_user
from app.db.mongo import get_db

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

# 1. AI Personal Learning Coach
@router.get('/ai/coach')
def learning_coach(user=Depends(current_user)):
    s=student_stats(uid(user)); db=get_db()
    recommendations=[]
    if s['weak_topics']:
        recommendations.append({'title':'Fix your weakest topics','description':f"Start with {', '.join(s['weak_topics'][:3])}.",'action':'practice'})
    if s['average_score'] and s['average_score'] < 70:
        recommendations.append({'title':'Take a focused practice quiz','description':'Your recent scores suggest a short revision test will help.','action':'quiz'})
    if s['completed_lessons']==0:
        recommendations.append({'title':'Start your first lesson','description':'Complete one lesson today to start your learning streak.','action':'courses'})
    else:
        recommendations.append({'title':'Keep your momentum','description':'Complete one lesson and five review questions today.','action':'learn'})
    return {'generated_at':now(),'profile':s,'coach_message':f"Hi {user.get('name') or user.get('email','learner').split('@')[0]} 👋 Your learning coach has prepared a focused plan.",'recommendations':recommendations,'daily_goal':{'minutes':30,'lessons':1,'questions':5}}

# 2. AI-generated personalized quiz
@router.post('/ai/personalized-quiz')
def personalized_quiz(data:dict|None=None,user=Depends(current_user)):
    db=get_db(); s=student_stats(uid(user)); topic=(data or {}).get('topic') or (s['weak_topics'][0] if s['weak_topics'] else None)
    query={'is_published':True}
    if topic: query['$or']=[{'topic':{'$regex':re.escape(topic),'$options':'i'}},{'tags':{'$regex':re.escape(topic),'$options':'i'}},{'question':{'$regex':re.escape(topic),'$options':'i'}},{'text':{'$regex':re.escape(topic),'$options':'i'}}]
    qs=list(db.questions.find(query).limit(int((data or {}).get('count',5) or 5)))
    if not qs: qs=list(db.questions.find({'is_published':True}).limit(5))
    return {'title':f'Personalized {topic or "Practice"} Quiz','topic':topic or 'mixed','difficulty':'adaptive','questions':[clean(q) for q in qs],'reason': 'Selected from your learning history and available question bank.'}

# 3. AI study plan
@router.post('/ai/study-plan')
def study_plan(data:dict|None=None,user=Depends(current_user)):
    d=data or {}; goal=d.get('goal') or 'Improve my learning performance'; days=max(7,min(180,int(d.get('days',30) or 30))); minutes=max(15,min(240,int(d.get('minutes_per_day',45) or 45)))
    s=student_stats(uid(user)); weak=s['weak_topics'] or ['core concepts','practice','revision']
    phases=[]
    for i,topic in enumerate(weak[:4],1):
        start=((i-1)*days)//4+1; end=(i*days)//4
        phases.append({'week':i,'days':f'{start}-{max(start,end)}','focus':topic,'activities':['Learn one focused lesson','Ask AI for an explanation','Complete 5-10 practice questions','Review flashcards'],'minutes_per_day':minutes})
    return {'goal':goal,'duration_days':days,'minutes_per_day':minutes,'starting_level':d.get('level','adaptive'),'phases':phases,'weekly_review':'Take an adaptive test every 7 days and update the next phase from weak areas.'}

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
    skills=tracks.get(role,tracks['AI Engineer']); s=student_stats(uid(user)); completed=max(0,s['completed_lessons']); baseline=min(85,10+completed*3)
    return {'role':role,'overall_readiness':baseline,'skills':[{'name':x,'score':min(100,max(10,baseline-(i*6))),'status':'strong' if baseline-(i*6)>=70 else 'developing' if baseline-(i*6)>=40 else 'start'} for i,x in enumerate(skills)],'next_steps':skills[:3]}

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

# 9. Global semantic-style search (token scoring, dependency-free)
@router.get('/search')
def global_search(q:str='',limit:int=20,user=Depends(current_user)):
    q=q.strip();
    if len(q)<2: return {'query':q,'results':[]}
    tokens=set(re.findall(r'\w+',q.lower())); db=get_db(); results=[]
    for collection,kind,fields in [('courses','course',['name','title','description','category','exam']),('lessons','lesson',['title','description','content']),('questions','question',['question','text','topic'])]:
        for x in db[collection].find({}).limit(1000):
            text=' '.join(str(x.get(f,'')) for f in fields).lower(); score=sum(1 for t in tokens if t in text)
            if score: results.append({'type':kind,'id':str(x.get('_id')),'title':x.get('name') or x.get('title') or x.get('question') or x.get('text') or 'Result','snippet':text[:180],'score':score})
    results.sort(key=lambda x:(-x['score'],x['title']))
    return {'query':q,'results':results[:max(1,min(limit,50))]}

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
