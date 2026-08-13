from pymongo import MongoClient
from pymongo.server_api import ServerApi
from app.config import MONGODB_URL, MONGODB_DATABASE

client = MongoClient(MONGODB_URL, server_api=ServerApi("1"))
db = client[MONGODB_DATABASE]

users_collection = db["users"]
courses_collection = db["courses"]
subjects_collection = db["subjects"]
lessons_collection = db["lessons"]
videos_collection = db["videos"]
quizzes_collection = db["quizzes"]
questions_collection = db["questions"]
quiz_attempts_collection = db["quiz_attempts"]
student_progress_collection = db["student_progress"]
bookmarks_collection = db["bookmarks"]
achievements_collection = db["achievements"]
notifications_collection = db["notifications"]

def ping_database():
    client.admin.command("ping")
    return True
