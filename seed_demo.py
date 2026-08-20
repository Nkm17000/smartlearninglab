"""Idempotent demo content for Smart Learning Lab.
Creates a complete free English Spoken course with modules, lessons and quizzes.
"""
from datetime import datetime, timezone
import uuid
from app.db.mongo import get_db


def now(): return datetime.now(timezone.utc)
def make_id(): return uuid.uuid4().hex

def upsert(collection, key, doc):
    db=get_db(); existing=db[collection].find_one(key)
    if existing:
        db[collection].update_one({"_id":existing["_id"]},{"$set":doc})
        return existing["_id"]
    doc={"_id":make_id(),"created_at":now(),"updated_at":now(),**doc}
    db[collection].insert_one(doc); return doc["_id"]


def main():
    db=get_db()
    course_id=upsert("courses",{"slug":"english-spoken"},{
        "slug":"english-spoken","name":"English Spoken","title":"English Spoken","short_description":"A practical beginner course for everyday spoken English.",
        "description":"Build confidence in greetings, introductions, daily conversations, grammar and workplace English through short lessons and practice tests.",
        "category":"English","exam":"General","level":"Beginner","language":"English","is_free":True,"is_published":True,"featured":True,
        "instructor_name":"Smart Learning Lab","estimated_minutes":180,"learning_objectives":["Introduce yourself confidently","Handle daily conversations","Build correct basic sentences","Improve practical vocabulary"],
        "prerequisites":["Basic English alphabet and words"],"tags":["spoken english","english grammar","conversation"],"rating":5,"review_count":0,"students_count":0,"video_count":12,"pdf_count":4,"mock_test_count":3,
    })
    modules=[
        ("English Foundations","Greetings, introductions and sentence basics.",["Use common greetings","Introduce yourself"],[("Greetings and Introductions","Learn hello, good morning, nice to meet you and polite responses.","Hello! Good morning. My name is Nitin. Nice to meet you.") ,("Talking About Yourself","Practice your name, city, job and interests.","My name is ___. I am from ___. I work as a ___.")]),
        ("Daily Conversations","Useful English for everyday situations.",["Ask and answer simple questions","Use polite requests"],[("At a Shop","Practice buying something and asking the price.","How much is this? I would like two, please.") ,("At Work","Practice simple workplace conversations.","Could you please help me? I will send the details today.")]),
        ("Grammar Basics","Build accurate spoken sentences.",["Use present tense correctly","Understand common sentence patterns"],[("Simple Present","Learn subject + verb patterns for routines.","I work every day. She works in Jaipur.") ,("Common Mistakes","Fix frequent spoken English errors.","I am working here. I have worked here for five years.")]),
    ]
    quiz_ids=[]
    for mi,(mname,mdesc,objs,lessons) in enumerate(modules,1):
        mid=upsert("topics",{"course_id":str(course_id),"name":mname},{"course_id":str(course_id),"name":mname,"title":mname,"description":mdesc,"learning_objectives":objs,"order":mi,"is_published":True})
        for li,(title,desc,content) in enumerate(lessons,1):
            upsert("lessons",{"topic_id":str(mid),"title":title},{"course_id":str(course_id),"topic_id":str(mid),"title":title,"name":title,"description":desc,"content":content,"duration_minutes":12,"resources":[f"{title} practice worksheet"],"video_url":"","is_published":True,"order":li})
    questions=[]
    for qtext,opts,ans,diff,exp in [
        ("Which sentence is correct?",["I work in Jaipur.","I works in Jaipur.","I working Jaipur.","I am work Jaipur."],0,"Use I + base verb in the simple present."),
        ("Choose the best greeting for the morning.",["Good morning!","Good night!","Goodbye!","See you yesterday!"],0,"Good morning is used before noon."),
        ("Choose the correct question.",["How much is this?","How much this is?","How this much is?","This is how much?"],0,"How much is this? is the standard question."),
        ("Complete: She ___ in Jaipur.",["work","works","working","worked"],1,"Third-person singular uses works in the simple present."),
    ]:
        qid=upsert("questions",{"question":qtext},{"question":qtext,"type":"mcq","options":opts,"correct_answer":ans,"answer":ans,"difficulty":diff,"marks":1,"negative_marks":0,"explanation":exp,"tags":["english"],"created_by":"seed_demo"})
        questions.append(str(qid))
    quiz_id=upsert("quizzes",{"course_id":str(course_id),"title":"English Foundations Mock Test"},{"course_id":str(course_id),"title":"English Foundations Mock Test","name":"English Foundations Mock Test","description":"A short practice test covering the first English modules.","duration_minutes":15,"passing_percentage":60,"question_ids":questions,"is_published":True,"featured":True})
    quiz_ids.append(quiz_id)
    db.courses.update_one({"_id":course_id},{"$set":{"mock_test_count":len(quiz_ids),"updated_at":now()}})
    print("Demo course seeded:", course_id)

if __name__ == "__main__": main()
