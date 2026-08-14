from fastapi import APIRouter
from app.database import ping_database
router=APIRouter()

@router.get("/health")
def health():
    try:
        ping_database()
        return {"status":"success","api":"up","database":"connected"}
    except Exception as exc:
        return {"status":"error","api":"up","database":"disconnected","detail":str(exc)}
