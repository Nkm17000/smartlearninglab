"""Smart Learning Lab full demo seed.

Run from the backend project root:
    python seed.py

It is idempotent for the main demo records and does not delete existing data.
"""
from datetime import datetime, timezone, timedelta
import uuid
from app.db.mongo import get_db
from app.core.security import hash_password

def now(): return datetime.now(timezone.utc)
def upsert(col,key,doc):
    db=get_db(); old=db[col].find_one(key)
    if old:
        db[col].update_one({'_id':old['_id']},{'$set':{**doc,'updated_at':now()}}); return old['_id']
    d={'_id':uuid.uuid4().hex,'created_at':now(),'updated_at':now(),**doc}; db[col].insert_one(d); return d['_id']

def main():
    db=get_db()
    accounts=[
      ('Smart Learning Root Admin','admin@smartlearninglab.com','ChangeMe123!','root_admin'),
      ('Demo Student','nitin@example.com','Password123!','student'),
      ('Demo Content Admin','content@smartlearninglab.com','Admin123!','content_admin'),
      ('Demo Instructor','instructor@smartlearninglab.com','Instructor123!','instructor')
    ]
    ids={}
    for name,email,password,role in accounts:
        ids[email]=upsert('users',{'email':email},{'email':email,'name':name,'password_hash':hash_password(password),'role':role,'is_active':True,'email_verified':True})
        print(f'{role}: {email} / {password}')

    course_id=upsert('courses',{'slug':'english-spoken'},{
      'slug':'english-spoken','name':'English Spoken','title':'English Spoken Mastery','short_description':'30-day practical spoken English program with conversation, grammar, vocabulary and mock tests.',
      'description':'Build confident spoken English through guided lessons, practice, revision, adaptive tests and interview-style speaking tasks.',
      'category':'English','exam':'General','level':'Beginner','language':'English','is_free':True,'is_published':True,'featured':True,
      'instructor_name':'Smart Learning Lab','estimated_minutes':900,'learning_objectives':['Speak confidently','Improve grammar','Build practical vocabulary','Handle workplace conversations'],'tags':['english','spoken english','communication'],'rating':4.8,'review_count':24,'students_count':1,'video_count':12,'pdf_count':4,'mock_test_count':3})

    modules=[('English Foundations','Greetings, introductions and sentence basics.'),('Daily Conversations','Everyday situations and polite requests.'),('Grammar & Vocabulary','Accuracy, vocabulary and revision.'),('Workplace Communication','Meetings, email and interview communication.')]
    lesson_ids=[]
    for mi,(name,desc) in enumerate(modules,1):
        mid=upsert('topics',{'course_id':str(course_id),'name':name},{'course_id':str(course_id),'name':name,'title':name,'description':desc,'order':mi,'is_published':True})
        for li in range(1,4):
            title=f'{name}: Lesson {li}'
            lid=upsert('lessons',{'topic_id':str(mid),'title':title},{'course_id':str(course_id),'topic_id':str(mid),'title':title,'name':title,'description':f'Practical lesson {li} for {name}.','content':f'{title}. Learn the concept, study examples, practise aloud and complete the lesson quiz.','duration_minutes':15,'order':li,'is_published':True,'video_url':'https://example.com/demo-video','resources':['Practice worksheet','Lesson notes']})
            lesson_ids.append(lid)

    qs=[
      ('Which sentence is correct?',['I work in Jaipur.','I works in Jaipur.','I working Jaipur.','I am work Jaipur.'],0,'easy'),
      ('Choose the best morning greeting.',['Good morning!','Good night!','Goodbye!','See you yesterday!'],0,'easy'),
      ('Choose the correct question.',['How much is this?','How much this is?','How this much is?','This is how much?'],0,'easy'),
      ('Complete: She ___ in Jaipur.',['work','works','working','worked'],1,'medium'),
      ('Which sentence uses present perfect correctly?',['I have finished the work.','I have finish the work.','I finished have the work.','I has finished the work.'],0,'medium'),
      ('Which is most appropriate in a professional meeting?',['Could you please clarify that?','You explain now!','What you saying?','Tell again quickly!'],0,'hard'),
    ]
    qids=[]
    for qtext,opts,ans,diff in qs:
        qid=upsert('questions',{'question':qtext},{'course_id':str(course_id),'topic_id':None,'question':qtext,'type':'mcq','options':opts,'correct_answer':ans,'answer':ans,'difficulty':diff,'marks':1,'negative_marks':0,'explanation':'Review the grammar and communication rule behind the correct option.','tags':['english',diff],'is_published':True})
        qids.append(str(qid))

    quiz_id=upsert('quizzes',{'course_id':str(course_id),'title':'English Adaptive Mock Test'},{'course_id':str(course_id),'title':'English Adaptive Mock Test','name':'English Adaptive Mock Test','description':'Practice test used by the demo student for results and adaptive learning.','duration_minutes':20,'passing_percentage':60,'max_attempts':5,'question_ids':qids,'is_published':True,'featured':True})
    db.courses.update_one({'_id':course_id},{'$set':{'mock_test_count':1}})

    student=str(ids['nitin@example.com'])
    # Enrollment and progress
    upsert('enrollments',{'user_id':student,'course_id':str(course_id)},{'user_id':student,'course_id':str(course_id),'status':'active','created_at':now()})
    for lid in lesson_ids[:4]:
        upsert('progress',{'user_id':student,'lesson_id':str(lid)},{'user_id':student,'course_id':str(course_id),'lesson_id':str(lid),'completed':True,'completed_at':now(),'updated_at':now()})
        upsert('video_progress',{'user_id':student,'lesson_id':str(lid)},{'user_id':student,'lesson_id':str(lid),'seconds':900,'duration_seconds':900,'completed':True,'updated_at':now()})

    # Sample quiz attempt
    attempt_id=upsert('test_attempts',{'user_id':student,'test_id':str(quiz_id),'status':'submitted'},{'user_id':student,'test_id':str(quiz_id),'status':'submitted','started_at':now()-timedelta(minutes=18),'submitted_at':now(),'result':{'score':5,'total':6,'percentage':83.33,'passed':True,'correct_count':5,'wrong_count':1}})

    # Flashcards
    for front,back in [('Present perfect','have/has + past participle'),('Could you please...?','Polite request used in professional communication.'),('Accomplish','To successfully complete something.')]:
        upsert('flashcards',{'user_id':student,'front':front},{'user_id':student,'front':front,'back':back,'course_id':str(course_id),'ease':2.5,'interval_days':1,'repetitions':0,'due_at':now()})

    # Community
    post_id=upsert('community_posts',{'user_id':student,'title':'How can I improve speaking fluency?'},{'user_id':student,'author_name':'Demo Student','title':'How can I improve speaking fluency?','content':'I can write English fairly well. What daily routine would you recommend for speaking practice?','course_id':str(course_id),'likes':3,'status':'active'})
    upsert('community_comments',{'post_id':str(post_id),'user_id':str(ids['instructor@smartlearninglab.com'])},{'post_id':str(post_id),'user_id':str(ids['instructor@smartlearninglab.com']),'author_name':'Demo Instructor','content':'Try 10 minutes of speaking aloud every day and review your mistakes after each practice session.'})

    # Activity for analytics
    for i,event in enumerate(['course_view','lesson_completed','quiz_completed','flashcard_review','speaking_practice']):
        db.activity_events.insert_one({'_id':uuid.uuid4().hex,'user_id':student,'event':event,'course_id':str(course_id),'created_at':now()-timedelta(days=i)})

    # Course resources
    for i,lid in enumerate(lesson_ids[:3]):
        upsert('lesson_resources',{'lesson_id':str(lid),'title':'Study Notes'},{'lesson_id':str(lid),'title':'Study Notes','url':'https://example.com/study-notes.pdf','type':'pdf','duration_seconds':0,'order':i})

    print('\nDemo content ready.')
    print('Root Admin: admin@smartlearninglab.com / ChangeMe123!')
    print('Student:    nitin@example.com / Password123!')
    print('Content Admin: content@smartlearninglab.com / Admin123!')
    print('Instructor: instructor@smartlearninglab.com / Instructor123!')
    print('Course:',course_id,'Quiz:',quiz_id)

if __name__=='__main__': main()
