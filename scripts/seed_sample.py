import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import collection
from app.security import hash_password
from app.utils import now

def ensure_user(name,email,password,role):
    if not collection("users").find_one({"email":email}):
        collection("users").insert_one({"name":name,"email":email,"password_hash":hash_password(password),
                                        "role":role,"created_at":now()})

ensure_user("Smart Learning Admin","admin@smartlearninglab.com","Admin@12345","admin")
ensure_user("Nitin","student@smartlearninglab.com","Student@12345","student")

if collection("courses").count_documents({})==0:
    courses=[
      {"title":"Data Structures","subtitle":"Learn fundamentals and algorithms.","description":"Arrays, linked lists, stacks, queues and trees.","is_published":True,"progress":72},
      {"title":"Database Systems","subtitle":"SQL and data modeling.","description":"Database fundamentals and practical SQL.","is_published":True,"progress":50},
      {"title":"Operating Systems","subtitle":"Processes, memory and files.","description":"Understand OS fundamentals.","is_published":True,"progress":38},
      {"title":"Computer Networks","subtitle":"Protocols and networking.","description":"Networking fundamentals.","is_published":True,"progress":22},
      {"title":"Web Development","subtitle":"Build modern web applications.","description":"Frontend and backend web development.","is_published":True,"progress":15}
    ]
    collection("courses").insert_many(courses)
print("Sample seed complete. Existing documents were not deleted.")
