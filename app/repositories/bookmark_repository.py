from app.database import collection
from app.utils import clean_doc, now

class BookmarkRepository:
    def list_for_user(self,user_id):
        return [clean_doc(x) for x in collection("bookmarks").find({"user_id":user_id}).sort("_id",-1)]
    def upsert(self,user_id,lesson_id,note):
        collection("bookmarks").update_one({"user_id":user_id,"lesson_id":lesson_id},
            {"$set":{"user_id":user_id,"lesson_id":lesson_id,"note":note,"updated_at":now()}},upsert=True)
        return clean_doc(collection("bookmarks").find_one({"user_id":user_id,"lesson_id":lesson_id}))
    def delete(self,user_id,lesson_id):
        collection("bookmarks").delete_one({"user_id":user_id,"lesson_id":lesson_id})
