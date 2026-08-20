from datetime import datetime, timezone
import uuid
from app.core.security import hash_password
from app.db.mongo import get_db

accounts=[
 {"name":"Smart Learning Root Admin","email":"admin@smartlearninglab.com","password":"ChangeMe123!","role":"root_admin"},
 {"name":"Demo Student","email":"nitin@example.com","password":"Password123!","role":"student"},
]
db=get_db()
for a in accounts:
    now=datetime.now(timezone.utc)
    db.users.update_one(
        {"email":a["email"]},
        {"$set":{"name":a["name"],"password_hash":hash_password(a["password"]),"role":a["role"],"is_active":True,"updated_at":now},
         "$setOnInsert":{"_id":uuid.uuid4().hex,"email":a["email"],"created_at":now}},
        upsert=True)
    print(f'{a["role"]}: {a["email"]} / {a["password"]}')
print("Accounts ready. Existing learning content was not deleted.")
