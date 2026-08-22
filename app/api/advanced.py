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

# ---------- Gamification: profile + real game engine ----------
GAME_DEFS = {
    'daily-challenge': {'title':'Daily Challenge','game_type':'mcq','count':5,'time_limit_seconds':600,'xp_correct':20,'completion_bonus':40},
    'speed-quiz': {'title':'Speed Quiz','game_type':'mcq','count':8,'time_limit_seconds':60,'xp_correct':15,'completion_bonus':50},
    'flashcard-battle': {'title':'Flashcard Battle','game_type':'flashcard','count':5,'time_limit_seconds':300,'xp_correct':15,'completion_bonus':45},
    'match-learn': {'title':'Match & Learn','game_type':'match','count':5,'time_limit_seconds':300,'xp_correct':20,'completion_bonus':50},
    'word-scramble': {'title':'Word Scramble','game_type':'word_scramble','count':5,'time_limit_seconds':180,'xp_correct':25,'completion_bonus':60},
    'boss-battle': {'title':'Boss Battle','game_type':'mcq','count':10,'time_limit_seconds':600,'xp_correct':30,'completion_bonus':100},
}


def _game_questions(db, count, difficulty=None):
    q = {'is_published': True}
    if difficulty: q['difficulty'] = difficulty
    rows = list(db.questions.find(q).limit(100))
    if len(rows) < count:
        rows = list(db.questions.find({'is_published': True}).limit(200))
    # Prefer questions with options because the game engine is MCQ-first.
    rows = [x for x in rows if x.get('question') or x.get('text')]
    return rows[:count]


def _shuffle(values):
    import random
    values = list(values)
    random.shuffle(values)
    return values


def _word_from_question(q):
    # Prefer an explicit learning term if one exists; otherwise derive a
    # compact answer from the correct option. The answer itself is never sent
    # to the client until the server grades the submission.
    term = q.get('term') or q.get('word') or q.get('keyword')
    if term: return str(term).strip()
    options = q.get('options') or []
    idx = q.get('correct_answer', q.get('answer'))
    try:
        if isinstance(idx, int) and 0 <= idx < len(options):
            opt = options[idx]
            return str(opt.get('text') if isinstance(opt, dict) else opt).strip()
    except Exception:
        pass
    text = str(q.get('question') or q.get('text') or '').strip()
    words = re.findall(r'[A-Za-z]{4,}', text)
    return words[0] if words else 'learning'


def _scramble(word):
    import random
    clean_word = re.sub(r'[^A-Za-z]', '', word).lower()
    if len(clean_word) < 4: return clean_word[::-1]
    chars = list(clean_word)
    for _ in range(5):
        random.shuffle(chars)
        out = ''.join(chars)
        if out != clean_word: return out
    return clean_word[::-1]


@router.get('/gamification')
def gamification(user=Depends(current_user)):
    db = get_db()
    user_id = uid(user)

    lessons = db.progress.count_documents({'user_id': user_id, 'completed': True})
    attempts = list(db.test_attempts.find({'user_id': user_id, 'status': 'submitted'}))
    passed = sum(1 for a in attempts if (a.get('result', {}) or {}).get('passed'))
    courses = db.enrollments.count_documents({'user_id': user_id, 'status': 'active'})
    game_rows = list(db.game_sessions.find({'user_id': user_id, 'status': 'completed'}))
    game_xp = sum(int(x.get('xp_earned', 0) or 0) for x in game_rows)
    game_wins = sum(1 for x in game_rows if x.get('passed'))
    xp = lessons * 10 + len(attempts) * 5 + passed * 50 + game_xp
    if lessons >= 1:
        xp += 10
    level = 1 + xp // 500

    badges = []
    rules = [
        (lessons >= 1, 'first_lesson', 'First Lesson', '📖'),
        (lessons >= 10, 'ten_lessons', '10 Lessons', '🎯'),
        (len(attempts) >= 5, 'test_taker', 'Test Taker', '📝'),
        (game_wins >= 1, 'game_winner', 'Game Winner', '🎮'),
        (len(game_rows) >= 10, 'arcade_regular', 'Arcade Regular', '🕹️'),
        (xp >= 500, 'rising_star', 'Rising Star', '⭐'),
    ]
    for ok, code, name, icon in rules:
        if ok:
            badges.append({'code': code, 'name': name, 'icon': icon})

    # Learning streak based on completed lesson dates.
    completed = list(db.progress.find({'user_id': user_id, 'completed': True}))
    active_dates = set()
    for p in completed:
        dt = p.get('completed_at') or p.get('updated_at') or p.get('created_at')
        if dt:
            try: active_dates.add(dt.date().isoformat())
            except Exception:
                try: active_dates.add(str(dt)[:10])
                except Exception: pass
    streak = 0
    cursor = datetime.now(timezone.utc).date()
    while cursor.isoformat() in active_dates:
        streak += 1
        cursor -= timedelta(days=1)

    # Compute a small real leaderboard from student activity. It is intentionally
    # derived from existing collections so no separate leaderboard migration is needed.
    students = list(db.users.find({'role': 'student'}, {'password_hash': 0}).limit(100))
    leaderboard = []
    for st_user in students:
        sid = str(st_user.get('_id'))
        lcount = db.progress.count_documents({'user_id': sid, 'completed': True})
        ats = list(db.test_attempts.find({'user_id': sid, 'status': 'submitted'}))
        spassed = sum(1 for a in ats if (a.get('result', {}) or {}).get('passed'))
        games = list(db.game_sessions.find({'user_id': sid, 'status': 'completed'}))
        sxp = lcount * 10 + len(ats) * 5 + spassed * 50 + sum(int(g.get('xp_earned', 0) or 0) for g in games)
        if lcount: sxp += 10
        leaderboard.append({
            'user_id': sid,
            'name': st_user.get('name') or st_user.get('full_name') or st_user.get('email', 'Student').split('@')[0],
            'xp': sxp
        })
    leaderboard.sort(key=lambda x: x['xp'], reverse=True)
    for i, row in enumerate(leaderboard[:5], 1):
        row['rank'] = i

    achievements = [
        {'icon': '🟢', 'title': 'Daily Starter', 'subtitle': 'Play a game today'},
        {'icon': '🟠', 'title': 'Quick Learner', 'subtitle': 'Score 100% in any game'},
        {'icon': '🔴', 'title': 'Streak Keeper', 'subtitle': f'Maintain {max(3, streak)} day streak'},
        {'icon': '🔵', 'title': 'First Challenger', 'subtitle': 'Complete your first game'},
    ]

    return {
        'xp': xp, 'level': level, 'courses': courses, 'lessons': lessons,
        'tests': len(attempts), 'passed_tests': passed,
        'games_played': len(game_rows), 'games_won': game_wins, 'game_xp': game_xp,
        'streak_days': streak, 'best_streak': max(streak, 0),
        'high_score': max([int(g.get('score', 0) or 0) for g in game_rows] or [0]),
        'badges': badges, 'leaderboard': leaderboard, 'achievements': achievements
    }


@router.post('/gamification/games/{slug}/start')
def start_game(slug:str, data:dict|None=None, user=Depends(current_user)):
    db=get_db(); user_id=uid(user); definition=GAME_DEFS.get(slug)
    if not definition: raise HTTPException(404,'Game not found')
    import random
    count=definition['count']
    game_type=definition['game_type']
    items=[]

    if game_type == 'flashcard':
        cards=list(db.flashcards.find({'user_id':user_id}).sort('due_at',1).limit(max(count,20)))
        if not cards:
            # Fall back to published questions so a new learner can still play.
            qs=_game_questions(db,count)
            for q in qs:
                opts=q.get('options') or []
                idx=q.get('correct_answer',q.get('answer'))
                try:
                    back=opts[int(idx)] if isinstance(idx,(int,str)) and str(idx).isdigit() else q.get('answer','Review this concept')
                except Exception: back=q.get('answer','Review this concept')
                if isinstance(back,dict): back=back.get('text') or back.get('label') or back.get('value')
                cards.append({'_id':uuid.uuid4().hex,'front':q.get('question') or q.get('text'),'back':back or 'Review this concept'})
        cards=cards[:count]
        items=[{'id':str(c.get('_id')),'front':str(c.get('front','')),'back':str(c.get('back',''))} for c in cards]

    elif game_type == 'word_scramble':
        qs=_game_questions(db,count)
        seen=set()
        for q in qs:
            word=_word_from_question(q)
            key=word.lower()
            if len(key)<3 or key in seen: continue
            seen.add(key); items.append({'id':str(q.get('_id')),'scrambled':_scramble(word)})
            if len(items)>=count: break

    elif game_type == 'match':
        qs=_game_questions(db,count)
        for q in qs:
            opts=q.get('options') or []
            idx=q.get('correct_answer',q.get('answer'))
            try: idx=int(idx)
            except Exception: continue
            if not isinstance(opts,list) or not (0<=idx<len(opts)): continue
            correct=opts[idx]
            if isinstance(correct,dict): correct=correct.get('text') or correct.get('label') or correct.get('value')
            rights=[]
            for o in opts:
                rights.append(o.get('text') if isinstance(o,dict) else str(o))
            rights=_shuffle(rights)
            items.append({'id':str(q.get('_id')),'left':q.get('question') or q.get('text'),'right_options':rights})
            if len(items)>=count: break

    else:
        qs=_game_questions(db,count)
        for q in qs:
            options=q.get('options') or []
            normalized=[]
            for o in options:
                normalized.append(o.get('text') if isinstance(o,dict) else str(o))
            if not normalized: continue
            item={'id':str(q.get('_id')),'question':q.get('question') or q.get('text'),'options':normalized}
            items.append(item)
            if len(items)>=count: break

    if not items: raise HTTPException(404,'Not enough published learning content to start this game.')
    session_id=uuid.uuid4().hex
    d={'_id':session_id,'user_id':user_id,'slug':slug,'title':definition['title'],'game_type':game_type,
       'status':'started','current_index':0,'score':0,'correct_count':0,'wrong_count':0,'xp_earned':0,
       'items':items,'total':len(items),'time_limit_seconds':definition['time_limit_seconds'],'started_at':now(),
       'created_at':now()}
    # Store private answer metadata separately from public session items.
    if game_type in ('mcq','match','word_scramble'):
        d['answer_keys']={}
        for q in _game_questions(db, count):
            qid=str(q.get('_id'))
            if game_type=='word_scramble':
                word=_word_from_question(q); d['answer_keys'][qid]=word.strip().lower()
            else:
                expected=q.get('correct_answer',q.get('answer'))
                if game_type=='match':
                    opts=q.get('options') or []
                    try: expected=str(opts[int(expected)].get('text') if isinstance(opts[int(expected)],dict) else opts[int(expected)])
                    except Exception: expected=str(expected)
                d['answer_keys'][qid]=str(expected)
    db.game_sessions.insert_one(d)
    public={k:d[k] for k in ('_id','slug','title','game_type','current_index','score','total','time_limit_seconds')}
    public['session_id']=session_id; public['description']=f"{definition['title']} • {len(items)} rounds"
    public['items']=items
    return public


@router.post('/gamification/sessions/{session_id}/answer')
def answer_game(session_id:str,data:dict,user=Depends(current_user)):
    db=get_db(); user_id=uid(user); s=db.game_sessions.find_one({'_id':session_id,'user_id':user_id})
    if not s: raise HTTPException(404,'Game session not found')
    if s.get('status')!='started': return {'finished':True,'status':s.get('status'),'score':s.get('score',0),'xp_earned':s.get('xp_earned',0)}
    idx=int(s.get('current_index',0)); items=s.get('items',[])
    if idx>=len(items): return finish_game(session_id,user)
    item=items[idx]; submitted=data.get('answer'); slug=s.get('slug'); game_type=s.get('game_type')
    key=s.get('answer_keys',{}).get(str(item.get('id')))
    correct=False; correct_index=None; explanation=''
    if game_type=='flashcard':
        quality=int(submitted or 0); correct=quality>=3; explanation='3 or 5 means the card was recalled well.'
        xp=15 if correct else 5
    elif game_type=='word_scramble':
        correct=str(submitted or '').strip().lower()==str(key or '').strip().lower(); xp=25 if correct else 5
        explanation=f"Correct word: {key}" if key else ''
    else:
        if game_type=='match':
            opts=item.get('right_options') or []; expected=str(key or '')
            try: selected=opts[int(submitted)]; correct=str(selected).strip()==expected.strip()
            except Exception: correct=False
            correct_index=next((i for i,o in enumerate(opts) if str(o).strip()==expected.strip()),None)
        else:
            try: correct=str(submitted)==str(key)
            except Exception: correct=False
            try: correct_index=int(key)
            except Exception: correct_index=None
        xp=30 if slug=='boss-battle' and correct else 20 if correct else 5
        qrow=db.questions.find_one({'_id':item.get('id')})
        explanation=str(qrow.get('explanation','')) if qrow else ''
    new_index=idx+1; score=int(s.get('score',0))+ (10 if correct else 0); correct_count=int(s.get('correct_count',0))+(1 if correct else 0); wrong_count=int(s.get('wrong_count',0))+(0 if correct else 1); xp_total=int(s.get('xp_earned',0))+xp
    finished=new_index>=len(items)
    status='completed' if finished else 'started'
    db.game_sessions.update_one({'_id':session_id},{'$set':{'current_index':new_index,'score':score,'correct_count':correct_count,'wrong_count':wrong_count,'xp_earned':xp_total,'status':status,'updated_at':now(),**({'completed_at':now(),'passed':correct_count>=max(1,int(len(items)*0.6))} if finished else {})}})
    passed = correct_count >= max(1, int(len(items) * 0.6))
    if finished:
        bonus=50 if slug=='boss-battle' else 30
        xp_total += bonus
        db.game_sessions.update_one({'_id':session_id},{'$set':{'xp_earned':xp_total,'passed':passed}})
    return {'correct':correct,'correct_index':correct_index,'explanation':explanation,'xp_earned':xp,'score':score,'current_index':new_index,'finished':finished,'total':len(items),'total_xp':xp_total,'passed':passed,'correct_count':correct_count,'wrong_count':wrong_count}


@router.post('/gamification/sessions/{session_id}/finish')
def finish_game(session_id:str,user=Depends(current_user)):
    db=get_db(); user_id=uid(user); s=db.game_sessions.find_one({'_id':session_id,'user_id':user_id})
    if not s: raise HTTPException(404,'Game session not found')
    if s.get('status')=='completed': return {'finished':True,'status':'completed','score':s.get('score',0),'xp_earned':s.get('xp_earned',0),'passed':s.get('passed',False),'correct':s.get('correct_count',0),'total':s.get('total',0)}
    correct=int(s.get('correct_count',0)); total=int(s.get('total',0)); passed=correct>=max(1,int(total*0.6))
    bonus=50 if s.get('slug')=='boss-battle' else 30
    xp=int(s.get('xp_earned',0))+bonus
    db.game_sessions.update_one({'_id':session_id},{'$set':{'status':'completed','passed':passed,'xp_earned':xp,'completed_at':now(),'updated_at':now()}})
    return {'finished':True,'status':'completed','score':s.get('score',0),'xp_earned':xp,'passed':passed,'correct':correct,'total':total}

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
