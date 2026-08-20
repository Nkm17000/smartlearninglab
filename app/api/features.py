from datetime import datetime, timezone, timedelta
import re, uuid, math, os, json, urllib.request
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.security import current_user, admin_user
from app.db.mongo import get_db

router = APIRouter(prefix='/api/v1', tags=['AI & Advanced Learning'])

def now(): return datetime.now(timezone.utc)
def uid(u): return str(u['_id'])
def clean(v):
    if isinstance(v, dict): return {k: clean(x) for k,x in v.items() if k not in {'password_hash'}}
    if isinstance(v, list): return [clean(x) for x in v]
    try:
        from bson import ObjectId
        if isinstance(v,ObjectId): return str(v)
    except Exception: pass
    return v.isoformat() if hasattr(v,'isoformat') else v

def get_doc(collection, item_id):
    db=get_db(); x=db[collection].find_one({'_id':item_id})
    if x: return x
    return None

# ---------------- AI Course Generator ----------------
COURSE_TEMPLATES={
    'english': ['Foundations','Daily Conversations','Grammar & Vocabulary','Workplace Communication','Final Practice'],
    'java': ['Java Foundations','OOP & Collections','Concurrency','Spring Boot','Interview Practice'],
    'python': ['Python Foundations','Data Structures','APIs & Automation','Data Analysis','Projects'],
    'ai': ['AI Foundations','Prompt Engineering','RAG','Agents','AI System Design']
}

def infer_track(text):
    t=text.lower()
    for k in COURSE_TEMPLATES:
        if k in t: return k
    return 'general'

@router.post('/admin/ai/generate-course')
def generate_course(data:dict, user=Depends(admin_user)):
    title=(data.get('title') or data.get('topic') or 'New Learning Course').strip()
    level=data.get('level','Beginner'); duration=int(data.get('duration_days',30) or 30); language=data.get('language','English')
    track=infer_track(title+' '+str(data.get('description','')))
    names=COURSE_TEMPLATES.get(track,['Foundations','Core Concepts','Practice','Advanced Topics','Final Assessment'])
    modules=[]
    for i,n in enumerate(names,1):
        modules.append({'title':f'{n}','description':f'Learn {n.lower()} through guided lessons and practice.','order':i,'lessons':[{'title':f'{n}: Lesson {j}','description':f'Practical {n.lower()} lesson {j}.','content':f'Learning objectives for {n}. Examples, explanations and practice activities.','duration_minutes':max(10,duration*60//(len(names)*3))} for j in range(1,4)]})
    return {'draft':True,'course':{'title':title,'name':title,'description':data.get('description',f'Complete {title} learning program.'),'level':level,'language':language,'estimated_days':duration,'learning_objectives':data.get('objectives',['Build practical understanding','Practice with assessments','Apply concepts confidently']),'modules':modules}}

@router.post('/admin/ai/generate-course/save')
def generate_and_save_course(data:dict, user=Depends(admin_user)):
    generated=generate_course(data,user)
    c=generated['course']; db=get_db(); cid=uuid.uuid4().hex
    db.courses.insert_one({'_id':cid,'slug':re.sub(r'[^a-z0-9]+','-',c['title'].lower()).strip('-')+'-'+cid[:6],'name':c['name'],'title':c['title'],'description':c['description'],'short_description':c['description'][:180],'level':c['level'],'language':c['language'],'category':data.get('category',infer_track(c['title']).title()),'is_free':True,'is_published':False,'featured':False,'learning_objectives':c['learning_objectives'],'estimated_minutes':c['estimated_days']*60,'created_at':now(),'updated_at':now(),'created_by':uid(user)})
    for m in c['modules']:
        mid=uuid.uuid4().hex; db.topics.insert_one({'_id':mid,'course_id':cid,'name':m['title'],'title':m['title'],'description':m['description'],'order':m['order'],'is_published':False,'created_at':now()})
        for j,l in enumerate(m['lessons'],1):
            db.lessons.insert_one({'_id':uuid.uuid4().hex,'course_id':cid,'topic_id':mid,'title':l['title'],'name':l['title'],'description':l['description'],'content':l['content'],'duration_minutes':l['duration_minutes'],'order':j,'is_published':False,'created_at':now()})
    return {'course_id':cid,'course':clean(db.courses.find_one({'_id':cid})),'message':'AI-generated draft course saved. Review and publish from Course Builder.'}

# ---------------- AI Quiz Generator ----------------
def make_question(topic, i, difficulty):
    templates=[
        (f'Which statement best describes {topic}?',[f'{topic} is a core concept used in practice.','It is unrelated to the subject.','It only applies to hardware.','None of these.'],0),
        (f'Which is a good practice when learning {topic}?',['Practice with examples.','Avoid exercises.','Memorize without understanding.','Skip revision.'],0),
        (f'What should you do first when studying {topic}?',['Understand the basic concept.','Take the final exam.','Ignore examples.','Delete your notes.'],0),
        (f'Which approach improves mastery of {topic}?',['Practice, feedback and revision.','Only reading once.','Never testing yourself.','Skipping difficult topics.'],0)
    ]
    q,opts,ans=templates[(i-1)%len(templates)]
    return {'_id':uuid.uuid4().hex,'question':q,'type':'mcq','options':opts,'correct_answer':ans,'answer':ans,'difficulty':difficulty,'marks':1,'negative_marks':0,'explanation':f'The correct answer reflects a practical learning approach for {topic}.','tags':[topic.lower(),difficulty]}

@router.post('/admin/ai/generate-quiz')
def generate_quiz(data:dict, user=Depends(admin_user)):
    topic=(data.get('topic') or 'General Learning').strip(); count=min(50,max(1,int(data.get('count',10) or 10))); difficulty=data.get('difficulty','medium').lower()
    return {'draft':True,'quiz':{'title':data.get('title',f'{topic} Practice Test'),'description':f'AI-generated practice test for {topic}.','duration_minutes':int(data.get('duration_minutes',count*2) or count*2),'passing_percentage':int(data.get('passing_percentage',60) or 60),'questions':[make_question(topic,i,difficulty) for i in range(1,count+1)]}}

@router.post('/admin/ai/generate-quiz/save')
def generate_and_save_quiz(data:dict, user=Depends(admin_user)):
    generated=generate_quiz(data,user); qz=generated['quiz']; db=get_db(); qids=[]
    for q in qz['questions']:
        qid=q['_id']; q['created_at']=now(); q['created_by']=uid(user); q['is_published']=False; db.questions.insert_one(q); qids.append(qid)
    qid=uuid.uuid4().hex; db.quizzes.insert_one({'_id':qid,'title':qz['title'],'name':qz['title'],'description':qz['description'],'duration_minutes':qz['duration_minutes'],'passing_percentage':qz['passing_percentage'],'question_ids':qids,'course_id':data.get('course_id'),'is_published':False,'created_at':now(),'created_by':uid(user)})
    return {'quiz_id':qid,'question_ids':qids,'message':'AI quiz draft saved. Review questions before publishing.'}

# ---------------- RAG Tutor ----------------
def tokenize(text): return set(re.findall(r'[a-zA-Z0-9]{3,}',(text or '').lower()))
def retrieve(query, course_id=None, limit=5):
    db=get_db(); qtokens=tokenize(query); docs=[]
    filt={'is_published':True}
    if course_id: filt['course_id']=course_id
    for l in db.lessons.find(filt):
        txt=' '.join(str(l.get(k,'')) for k in ('title','description','content'))
        overlap=len(qtokens & tokenize(txt));
        if overlap: docs.append((overlap,l))
    docs.sort(key=lambda x:x[0],reverse=True)
    return [d for _,d in docs[:limit]]

def llm_answer(question, contexts):
    key=os.getenv('OPENAI_API_KEY')
    if not key: return None
    model=os.getenv('OPENAI_MODEL','gpt-4o-mini')
    body=json.dumps({'model':model,'messages':[{'role':'system','content':'Answer only from the supplied study context. If context is insufficient, say so.'},{'role':'user','content':f'Context:\n{contexts}\n\nQuestion: {question}'}]}).encode()
    req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=body,headers={'Content-Type':'application/json','Authorization':f'Bearer {key}'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=25) as r: return json.loads(r.read()).get('choices',[{}])[0].get('message',{}).get('content')
    except Exception: return None

@router.post('/ai/tutor/rag')
def rag_tutor(data:dict,user=Depends(current_user)):
    question=(data.get('question') or data.get('message') or '').strip()
    if not question: raise HTTPException(422,'question is required')
    docs=retrieve(question,data.get('course_id'),5)
    contexts='\n\n'.join(f"{d.get('title')}: {d.get('content') or d.get('description','')}" for d in docs)
    answer=llm_answer(question,contexts)
    if not answer:
        if docs: answer='Based on your course material:\n\n'+'\n\n'.join(f"• {d.get('title')}: {d.get('content') or d.get('description','')}" for d in docs[:3])
        else: answer='I could not find enough matching material in the course knowledge base. Try asking about a specific lesson or topic.'
    return {'answer':answer,'sources':[{'lesson_id':str(d['_id']),'title':d.get('title'),'snippet':(d.get('content') or d.get('description',''))[:220]} for d in docs]}

# ---------------- Speaking Practice ----------------
@router.post('/ai/speaking/evaluate')
def speaking(data:dict,user=Depends(current_user)):
    transcript=(data.get('transcript') or '').strip(); target=data.get('target','General conversation')
    words=tokenize(transcript); n=len(transcript.split()); fillers=sum(transcript.lower().count(x) for x in ['um','uh','like'])
    grammar=max(40,min(98,70+min(20,n//8)-fillers*3)); vocab=max(35,min(98,55+len(words)*2)); fluency=max(35,min(98,60+n//4-fillers*4)); pronunciation=max(45,min(95,65+len(words)%25))
    overall=round((grammar+vocab+fluency+pronunciation)/4)
    return {'target':target,'transcript':transcript,'scores':{'grammar':grammar,'vocabulary':vocab,'fluency':fluency,'pronunciation':pronunciation,'overall':overall},'feedback':['Use complete sentences.','Add specific examples to make your answers stronger.','Practice speaking aloud for 5–10 minutes daily.']}

# ---------------- Personalized Learning Path ----------------
@router.get('/personalized/path')
def personalized_path(user=Depends(current_user)):
    db=get_db(); user_id=uid(user)
    attempts=list(db.test_attempts.find({'user_id':user_id,'status':'submitted'}))
    weak=[]
    for a in attempts:
        r=a.get('result',{}); pct=float(r.get('percentage',0));
        if pct<70: weak.append({'quiz_id':a.get('test_id'),'score':pct})
    enrolled=[e.get('course_id') for e in db.enrollments.find({'user_id':user_id,'status':'active'})]
    lessons=[]
    q={'is_published':True}
    if enrolled: q['course_id']={'$in':enrolled}
    for l in db.lessons.find(q).sort('order',1).limit(12): lessons.append(clean(l))
    return {'summary':'Personalized path based on your progress and weaker quiz results.','weak_areas':weak,'next_steps':lessons[:6],'daily_goal_minutes':20}

# ---------------- Adaptive Tests ----------------
@router.post('/adaptive/tests/submit')
def adaptive_submit(data:dict,user=Depends(current_user)):
    questions=data.get('questions') or []; answers=data.get('answers') or {}; correct=0; total=len(questions)
    for q in questions:
        qid=str(q.get('_id') or q.get('id')); expected=q.get('correct_answer',q.get('answer')); submitted=answers.get(qid)
        if submitted is not None and str(submitted)==str(expected): correct+=1
    pct=round(correct*100/total,2) if total else 0
    return {'correct':correct,'total':total,'percentage':pct,'passed':pct>=60,'next_level':'hard' if pct>=80 else 'medium' if pct>=60 else 'easy'}

@router.post('/adaptive/tests')
def adaptive_test(data:dict,user=Depends(current_user)):
    db=get_db(); course_id=data.get('course_id'); count=min(30,max(5,int(data.get('count',10) or 10)))
    attempts=list(db.test_attempts.find({'user_id':uid(user),'status':'submitted'}).sort('submitted_at',-1).limit(5)); avg=sum(float(a.get('result',{}).get('percentage',60)) for a in attempts)/len(attempts) if attempts else 60
    difficulty='hard' if avg>=80 else 'medium' if avg>=60 else 'easy'
    qs=list(db.questions.find({'is_published':True,**({'course_id':course_id} if course_id else {})}))
    same=[q for q in qs if str(q.get('difficulty','medium')).lower()==difficulty]; pool=same+qs
    seen=set(); chosen=[]
    for q in pool:
        sid=str(q['_id'])
        if sid not in seen: seen.add(sid); chosen.append(clean(q));
        if len(chosen)>=count: break
    return {'adaptive_level':difficulty,'prior_average':round(avg,2),'questions':[{k:v for k,v in q.items() if k not in ('correct_answer','answer')} for q in chosen]}

# ---------------- Flashcards + Spaced Repetition ----------------
@router.get('/flashcards')
def flashcards(user=Depends(current_user)):
    return [clean(x) for x in get_db().flashcards.find({'user_id':uid(user)}).sort('due_at',1)]

@router.post('/flashcards')
def create_flashcard(data:dict,user=Depends(current_user)):
    if not data.get('front') or not data.get('back'): raise HTTPException(422,'front and back are required')
    d={'_id':uuid.uuid4().hex,'user_id':uid(user),'front':data['front'],'back':data['back'],'course_id':data.get('course_id'),'ease':2.5,'interval_days':1,'repetitions':0,'due_at':now(),'created_at':now()}
    get_db().flashcards.insert_one(d); return clean(d)

@router.post('/flashcards/{card_id}/review')
def review_flashcard(card_id:str,data:dict,user=Depends(current_user)):
    db=get_db(); c=db.flashcards.find_one({'_id':card_id,'user_id':uid(user)})
    if not c: raise HTTPException(404,'Flashcard not found')
    quality=int(data.get('quality',3)); quality=max(0,min(5,quality)); ease=float(c.get('ease',2.5)); reps=int(c.get('repetitions',0)); interval=int(c.get('interval_days',1))
    if quality<3: reps=0; interval=1
    else:
        reps+=1; interval=1 if reps==1 else 6 if reps==2 else max(1,round(interval*ease))
        ease=max(1.3,ease+0.1-(5-quality)*(0.08+(5-quality)*0.02))
    d={'repetitions':reps,'interval_days':interval,'ease':ease,'due_at':now()+timedelta(days=interval),'last_quality':quality,'updated_at':now()}
    db.flashcards.update_one({'_id':card_id},{'$set':d}); return clean(db.flashcards.find_one({'_id':card_id}))

@router.get('/flashcards/due')
def due_flashcards(user=Depends(current_user)):
    return [clean(x) for x in get_db().flashcards.find({'user_id':uid(user),'due_at':{'$lte':now()}}).sort('due_at',1)]

# ---------------- Interview Preparation ----------------
INTERVIEW_TOPICS={'java':['Explain HashMap internals.','What is the difference between synchronized and Lock?','Explain JVM memory areas.'],'spring':['Explain dependency injection.','What is Spring Boot auto-configuration?','How do you design resilient microservices?'],'ai':['What is RAG?','Explain embeddings.','How would you evaluate an LLM application?'],'general':['Tell me about yourself.','Describe a difficult technical problem you solved.','How do you handle production incidents?']}

@router.get('/interview/topics')
def interview_topics(user=Depends(current_user)): return {'topics':list(INTERVIEW_TOPICS.keys())}

@router.post('/interview/session')
def interview_session(data:dict,user=Depends(current_user)):
    topic=str(data.get('topic','general')).lower(); questions=INTERVIEW_TOPICS.get(topic,INTERVIEW_TOPICS['general']); count=min(10,max(1,int(data.get('count',5) or 5)))
    sid=uuid.uuid4().hex; d={'_id':sid,'user_id':uid(user),'topic':topic,'questions':questions[:count],'created_at':now()}; get_db().interview_sessions.insert_one(d); return clean(d)

@router.post('/interview/evaluate')
def interview_evaluate(data:dict,user=Depends(current_user)):
    answer=str(data.get('answer','')); n=len(answer.split()); score=max(30,min(98,55+n*2)); return {'score':score,'strengths':['Clear structure' if n>=20 else 'Direct response'],'improvements':['Use a concrete example.','Explain the impact and result.'],'model_answer_hint':'Use Situation → Action → Result when answering behavioral questions.'}

# ---------------- Advanced Analytics ----------------
@router.get('/analytics/advanced')
def advanced_analytics(user=Depends(current_user)):
    db=get_db(); user_id=uid(user)
    enroll=db.enrollments.count_documents({'user_id':user_id}); lessons=db.progress.count_documents({'user_id':user_id,'completed':True}); attempts=list(db.test_attempts.find({'user_id':user_id,'status':'submitted'})); avg=round(sum(float(x.get('result',{}).get('percentage',0)) for x in attempts)/len(attempts),2) if attempts else 0
    activity=list(db.activity_events.find({'user_id':user_id}).sort('created_at',-1).limit(30))
    return {'courses_enrolled':enroll,'lessons_completed':lessons,'tests_taken':len(attempts),'average_score':avg,'recent_activity':[clean(x) for x in activity]}

@router.get('/admin/analytics/advanced')
def admin_advanced_analytics(user=Depends(admin_user)):
    db=get_db();
    courses=db.courses.count_documents({}); published=db.courses.count_documents({'is_published':True}); students=db.users.count_documents({'role':'student'}); enroll=db.enrollments.count_documents({}); attempts=db.test_attempts.count_documents({'status':'submitted'})
    scores=[float(x.get('result',{}).get('percentage',0)) for x in db.test_attempts.find({'status':'submitted'})]; avg=round(sum(scores)/len(scores),2) if scores else 0
    top=[]
    for c in db.courses.find({}).sort('students_count',-1).limit(10): top.append({'course':c.get('title') or c.get('name'),'students':c.get('students_count',0)})
    return {'courses':courses,'published_courses':published,'students':students,'enrollments':enroll,'quiz_attempts':attempts,'average_quiz_score':avg,'top_courses':top}

# ---------------- Community ----------------
@router.get('/community/posts')
def community_posts(course_id:str|None=None,limit:int=Query(50,ge=1,le=100),user=Depends(current_user)):
    q={'status':'active'}
    if course_id:q['course_id']=course_id
    return [clean(x) for x in get_db().community_posts.find(q).sort('created_at',-1).limit(limit)]

@router.post('/community/posts')
def create_post(data:dict,user=Depends(current_user)):
    if not data.get('title') or not data.get('content'): raise HTTPException(422,'title and content are required')
    d={'_id':uuid.uuid4().hex,'user_id':uid(user),'author_name':user.get('name') or user.get('email'),'title':data['title'],'content':data['content'],'course_id':data.get('course_id'),'likes':0,'status':'active','created_at':now()}; get_db().community_posts.insert_one(d); return clean(d)

@router.get('/community/posts/{post_id}/comments')
def comments(post_id:str,user=Depends(current_user)): return [clean(x) for x in get_db().community_comments.find({'post_id':post_id}).sort('created_at',1)]

@router.post('/community/posts/{post_id}/comments')
def add_comment(post_id:str,data:dict,user=Depends(current_user)):
    if not data.get('content'): raise HTTPException(422,'content is required')
    if not get_db().community_posts.find_one({'_id':post_id}): raise HTTPException(404,'Post not found')
    d={'_id':uuid.uuid4().hex,'post_id':post_id,'user_id':uid(user),'author_name':user.get('name') or user.get('email'),'content':data['content'],'created_at':now()}; get_db().community_comments.insert_one(d); return clean(d)

@router.post('/community/posts/{post_id}/like')
def like_post(post_id:str,user=Depends(current_user)):
    db=get_db(); p=db.community_posts.find_one({'_id':post_id})
    if not p: raise HTTPException(404,'Post not found')
    db.community_posts.update_one({'_id':post_id},{'$inc':{'likes':1}}); return {'likes':p.get('likes',0)+1}
