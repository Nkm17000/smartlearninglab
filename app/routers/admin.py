from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.dependencies import require_admin
from app.database import collection
from app.utils import clean_doc

router=APIRouter()

class CourseCreate(BaseModel):
    title:str=Field(min_length=2)
    description:str=""
    subtitle:str=""
    is_published:bool=True

@router.post("/courses")
def create_course(x:CourseCreate,user=Depends(require_admin)):
    doc={**x.model_dump(),"created_by":user["_id"]}
    r=collection("courses").insert_one(doc)
    return {"status":"success","data":clean_doc(collection("courses").find_one({"_id":r.inserted_id}))}

@router.get("/users")
def users(user=Depends(require_admin)):
    rows=[clean_doc(x) for x in collection("users").find({},{"password_hash":0,"password":0}).limit(500)]
    return {"status":"success","data":rows}
