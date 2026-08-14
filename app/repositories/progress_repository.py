from app.database import collection
from app.utils import clean_doc, now

class ProgressRepository:
    def list_for_user(self, user_id):
        q={"user_id":user_id}
        rows=list(collection("student_progress").find(q))
        if not rows:
            rows=list(collection("student_progress").find({"userId":user_id}))
        return [clean_doc(x) for x in rows]

    def upsert(self, user_id, data):
        q={"user_id":user_id,"lesson_id":data["lesson_id"]}
        doc={**data,"user_id":user_id,"updated_at":now()}
        collection("student_progress").update_one(q,{"$set":doc},upsert=True)
        return clean_doc(collection("student_progress").find_one(q))
