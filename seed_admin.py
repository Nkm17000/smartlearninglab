"""Create or reset demo admin/student accounts without deleting learning content."""
from app.db.mongo import get_db
from app.core.security import hash_password
import uuid
from datetime import datetime, timezone

accounts=[
    {"name":"Smart Learning Admin","email":"admin@smartlearninglab.com","password":"ChangeMe123!","role":"admin"},
    {"name":"Demo Student","email":"nitin@example.com","password":"Password123!","role":"student"},
]
for a in accounts:
    db=get_db(); email=a["email"]
    db.users.update_one({"email":email},{"$set":{"name":a["name"],"password_hash":hash_password(a["password"]),"role":a["role"],"is_active":True,"updated_at":datetime.now(timezone.utc)},"$setOnInsert":{"_id":uuid.uuid4().hex,"email":email,"created_at":datetime.now(timezone.utc)}},upsert=True)
    print(a["role"],email,a["password"])
print("Accounts ready. Existing content was not deleted.")
