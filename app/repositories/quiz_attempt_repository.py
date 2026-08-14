from app.database import collection
from app.utils import clean_doc, now

class QuizAttemptRepository:
    def list_for_user(self,user_id):
        return [clean_doc(x) for x in collection("quiz_attempts").find({"user_id":user_id}).sort("_id",-1).limit(50)]
    def insert(self,doc):
        doc["created_at"]=now()
        r=collection("quiz_attempts").insert_one(doc)
        return clean_doc(collection("quiz_attempts").find_one({"_id":r.inserted_id}))
