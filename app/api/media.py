from datetime import datetime, timezone
import mimetypes
import os
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from bson import ObjectId

from app.core.config import get_settings
from app.core.security import current_user, admin_user
from app.db.mongo import get_db

router = APIRouter(prefix='/api/v1', tags=['Media & Library'])

COURSE_CATEGORIES = [
    'SSC', 'Banking', 'UPSC', 'English Spoken', 'Railway',
    'Teaching', 'Defence', 'State Exams', 'Computer', 'General', 'Other'
]
RESOURCE_TYPES = {'video', 'audio', 'pdf', 'document', 'image', 'link', 'other'}
MAX_UPLOAD_MB = 500

def now(): return datetime.now(timezone.utc)
def uid(user): return str(user['_id'])

def clean(v):
    if isinstance(v, dict): return {k: clean(x) for k,x in v.items() if k != 'password_hash'}
    if isinstance(v, list): return [clean(x) for x in v]
    if isinstance(v, ObjectId): return str(v)
    if hasattr(v, 'isoformat'): return v.isoformat()
    return v

def find(collection, item_id):
    db=get_db(); x=db[collection].find_one({'_id':item_id})
    if x: return x
    try:
        if ObjectId.is_valid(item_id): return db[collection].find_one({'_id':ObjectId(item_id)})
    except Exception: pass
    return None

def infer_type(filename: str, content_type: str = ''):
    ext=os.path.splitext(filename.lower())[1]
    if content_type == 'application/pdf' or ext == '.pdf': return 'pdf'
    if content_type.startswith('video/') or ext in {'.mp4','.webm','.mov','.m4v','.mkv'}: return 'video'
    if content_type.startswith('audio/') or ext in {'.mp3','.wav','.m4a','.aac','.ogg','.flac'}: return 'audio'
    if content_type.startswith('image/') or ext in {'.jpg','.jpeg','.png','.webp','.gif','.svg'}: return 'image'
    if ext in {'.doc','.docx','.ppt','.pptx','.xls','.xlsx','.txt'}: return 'document'
    return 'other'

def _r2_client():
    s=get_settings()
    if not (s.r2_account_id and s.r2_access_key_id and s.r2_secret_access_key and s.r2_bucket_name):
        raise RuntimeError('R2 is not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME.')
    endpoint=s.r2_endpoint_url.strip() or f'https://{s.r2_account_id}.r2.cloudflarestorage.com'
    return boto3.client('s3', endpoint_url=endpoint, aws_access_key_id=s.r2_access_key_id, aws_secret_access_key=s.r2_secret_access_key, region_name='auto')

def _r2_key(prefix: str, filename: str) -> str:
    safe=os.path.basename(filename or 'upload')
    return f'{prefix.rstrip("/")}/{uuid.uuid4().hex}-{safe}'

def upload_file(upload: UploadFile, metadata: dict):
    filename=os.path.basename(upload.filename or f'upload-{uuid.uuid4().hex}')
    content_type=upload.content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    resource_type=metadata.get('type') or infer_type(filename,content_type)
    if resource_type not in RESOURCE_TYPES: resource_type='other'
    course_id=metadata.get('course_id'); lesson_id=metadata.get('lesson_id'); owner_type=metadata.get('owner_type','library')
    if course_id: prefix=f'courses/{course_id}/{resource_type}s'
    elif lesson_id: prefix=f'lessons/{lesson_id}/{resource_type}s'
    else: prefix=f'library/{resource_type}s'
    key=_r2_key(prefix,filename)
    s=get_settings(); client=_r2_client()
    try:
        upload.file.seek(0)
        client.upload_fileobj(upload.file,s.r2_bucket_name,key,ExtraArgs={'ContentType':content_type,'Metadata':{'resource_type':resource_type,'owner_type':owner_type}})
    except (BotoCoreError,ClientError) as exc:
        raise RuntimeError(f'R2 upload failed: {exc}') from exc
    return uuid.uuid4().hex, filename, content_type, resource_type, key

def upload_bytes(raw: bytes, filename: str, content_type: str, metadata: dict):
    import io
    resource_type=metadata.get('type') or infer_type(filename,content_type)
    if resource_type not in RESOURCE_TYPES: resource_type='other'
    course_id=metadata.get('course_id'); owner_type=metadata.get('owner_type','library')
    prefix=f'courses/{course_id}/{resource_type}s' if course_id else f'library/{resource_type}s'
    key=_r2_key(prefix,filename)
    s=get_settings(); client=_r2_client()
    try:
        client.upload_fileobj(io.BytesIO(raw),s.r2_bucket_name,key,ExtraArgs={'ContentType':content_type,'Metadata':{'resource_type':resource_type,'owner_type':owner_type}})
    except (BotoCoreError,ClientError) as exc:
        raise RuntimeError(f'R2 upload failed: {exc}') from exc
    return uuid.uuid4().hex, os.path.basename(filename), content_type, resource_type, key

def _signed_url(key: str, download: bool=False, filename: str='download') -> str:
    s=get_settings(); client=_r2_client()
    params={'Bucket':s.r2_bucket_name,'Key':key}
    if download:
        safe=filename.replace('"','')
        params['ResponseContentDisposition']=f'attachment; filename="{safe}"'
    else:
        params['ResponseContentDisposition']=f'inline; filename="{filename.replace(chr(34), "")}"'
    params['ResponseContentType']=mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    return client.generate_presigned_url('get_object',Params=params,ExpiresIn=max(60,min(604800,s.r2_signed_url_expiry)))

def _find_media(media_id: str):
    db=get_db()
    for collection in ('course_resources','lesson_resources','learning_library'):
        doc=db[collection].find_one({'media_id':media_id})
        if doc: return doc
    # bulk/imported course may only reference source_pdf_media_id
    doc=db.courses.find_one({'source_pdf_media_id':media_id})
    return doc

def _delete_media(media_id: str):
    doc=_find_media(media_id)
    if not doc: return
    key=doc.get('storage_key')
    if key:
        try: _r2_client().delete_object(Bucket=get_settings().r2_bucket_name,Key=key)
        except Exception: pass

@router.get('/storage/health')
def storage_health(user=Depends(admin_user)):
    s=get_settings()
    try:
        _r2_client().head_bucket(Bucket=s.r2_bucket_name)
        return {'storage':'r2','status':'connected','bucket':s.r2_bucket_name}
    except Exception as exc:
        raise HTTPException(503,f'R2 storage unavailable: {exc}')

@router.get('/admin/course-categories')
def admin_course_categories(user=Depends(admin_user)): return {'categories':COURSE_CATEGORIES}

def _resource_doc(course_id, lesson_id, title, description, filename, content_type, kind, media_id, key, user, order):
    return {'_id':uuid.uuid4().hex,'course_id':course_id,'lesson_id':lesson_id,'title':title.strip() or filename,'description':description.strip(),'url':f'/api/v1/media/{media_id}','media_id':media_id,'storage':'r2','storage_key':key,'filename':filename,'content_type':content_type,'type':kind,'source':'upload','order':order,'created_at':now(),'created_by':uid(user)}

@router.post('/admin/courses/{course_id}/resources/upload')
def upload_course_resource(course_id:str,file:UploadFile=File(...),title:str='',resource_type:str='',description:str='',user=Depends(admin_user)):
    course=find('courses',course_id)
    if not course: raise HTTPException(404,'Course not found')
    if not file.filename: raise HTTPException(422,'File is required')
    if resource_type and resource_type not in RESOURCE_TYPES: raise HTTPException(422,'Unsupported resource type')
    try: media_id,filename,content_type,inferred,key=upload_file(file,{'owner_type':'course','course_id':course_id,'uploaded_by':uid(user),'type':resource_type or None})
    except RuntimeError as exc: raise HTTPException(503,str(exc))
    kind=resource_type or inferred; db=get_db()
    doc=_resource_doc(course_id,None,title,description,filename,content_type,kind,media_id,key,user,db.course_resources.count_documents({'course_id':course_id})+1)
    db.course_resources.insert_one(doc); db.courses.update_one({'_id':course.get('_id')},{'$inc':{f'{kind}_count':1}})
    return clean(doc)

@router.post('/admin/courses/{course_id}/resources')
def create_course_resource(course_id:str,data:dict,user=Depends(admin_user)):
    course=find('courses',course_id)
    if not course: raise HTTPException(404,'Course not found')
    title=str(data.get('title','')).strip(); url=str(data.get('url','')).strip(); kind=str(data.get('type','link')).lower()
    if not title or not url: raise HTTPException(422,'title and url are required')
    if kind not in RESOURCE_TYPES: raise HTTPException(422,'Unsupported resource type')
    doc={'_id':uuid.uuid4().hex,'course_id':course_id,'title':title,'description':str(data.get('description','')).strip(),'url':url,'type':kind,'source':'url','order':get_db().course_resources.count_documents({'course_id':course_id})+1,'created_at':now(),'created_by':uid(user)}
    get_db().course_resources.insert_one(doc); return clean(doc)

@router.get('/admin/courses/{course_id}/resources')
def admin_course_resources(course_id:str,user=Depends(admin_user)):
    if not find('courses',course_id): raise HTTPException(404,'Course not found')
    return [clean(x) for x in get_db().course_resources.find({'course_id':course_id}).sort('order',1)]

@router.delete('/admin/courses/{course_id}/resources/{resource_id}')
def delete_course_resource(course_id:str,resource_id:str,user=Depends(admin_user)):
    db=get_db(); resource=db.course_resources.find_one({'_id':resource_id,'course_id':course_id})
    if not resource: raise HTTPException(404,'Course resource not found')
    _delete_media(resource.get('media_id','')); db.course_resources.delete_one({'_id':resource_id})
    kind=resource.get('type')
    if kind in RESOURCE_TYPES: db.courses.update_one({'_id':find('courses',course_id)['_id']},{'$inc':{f'{kind}_count':-1}})
    return {'message':'Course resource deleted'}

@router.post('/admin/lessons/{lesson_id}/resources/upload')
def upload_lesson_resource(lesson_id:str,file:UploadFile=File(...),title:str='',resource_type:str='',description:str='',user=Depends(admin_user)):
    lesson=find('lessons',lesson_id)
    if not lesson: raise HTTPException(404,'Lesson not found')
    if not file.filename: raise HTTPException(422,'File is required')
    if resource_type and resource_type not in RESOURCE_TYPES: raise HTTPException(422,'Unsupported resource type')
    try: media_id,filename,content_type,inferred,key=upload_file(file,{'owner_type':'lesson','lesson_id':lesson_id,'course_id':lesson.get('course_id'),'uploaded_by':uid(user),'type':resource_type or None})
    except RuntimeError as exc: raise HTTPException(503,str(exc))
    kind=resource_type or inferred; db=get_db()
    doc=_resource_doc(lesson.get('course_id'),lesson_id,title,description,filename,content_type,kind,media_id,key,user,db.lesson_resources.count_documents({'lesson_id':lesson_id})+1)
    db.lesson_resources.insert_one(doc); return clean(doc)

@router.post('/admin/library/upload')
def upload_library_file(file:UploadFile=File(...),title:str='',category:str='General',description:str='',tags:str='',user=Depends(admin_user)):
    if not file.filename: raise HTTPException(422,'File is required')
    try: media_id,filename,content_type,inferred,key=upload_file(file,{'owner_type':'library','uploaded_by':uid(user),'category':category or 'General'})
    except RuntimeError as exc: raise HTTPException(503,str(exc))
    doc={'_id':uuid.uuid4().hex,'title':title.strip() or filename,'description':description.strip(),'category':category.strip() or 'General','tags':[x.strip() for x in tags.split(',') if x.strip()],'filename':filename,'content_type':content_type,'type':inferred,'media_id':media_id,'storage':'r2','storage_key':key,'url':f'/api/v1/media/{media_id}','is_published':True,'created_at':now(),'created_by':uid(user)}
    get_db().learning_library.insert_one(doc); return clean(doc)

@router.post('/admin/library')
def create_library_link(data:dict,user=Depends(admin_user)):
    title=str(data.get('title','')).strip(); url=str(data.get('url','')).strip(); kind=str(data.get('type','pdf')).lower()
    if not title or not url: raise HTTPException(422,'title and url are required')
    if kind not in RESOURCE_TYPES: raise HTTPException(422,'Unsupported resource type')
    doc={'_id':uuid.uuid4().hex,'title':title,'description':str(data.get('description','')).strip(),'category':str(data.get('category','General')).strip() or 'General','tags':data.get('tags',[]) or [],'type':kind,'url':url,'source':'url','is_published':True,'created_at':now(),'created_by':uid(user)}
    get_db().learning_library.insert_one(doc); return clean(doc)

@router.get('/admin/library')
def admin_library(user=Depends(admin_user)): return [clean(x) for x in get_db().learning_library.find({}).sort('created_at',-1)]

@router.delete('/admin/library/{item_id}')
def delete_library(item_id:str,user=Depends(admin_user)):
    db=get_db(); item=db.learning_library.find_one({'_id':item_id})
    if not item: raise HTTPException(404,'Library item not found')
    _delete_media(item.get('media_id','')); db.learning_library.delete_one({'_id':item_id}); return {'message':'Library item deleted'}

@router.get('/library')
def student_library(category:str|None=None,user=Depends(current_user)):
    q={'is_published':True}
    if category: q['category']=category
    return [clean(x) for x in get_db().learning_library.find(q).sort('created_at',-1)]

@router.get('/library/categories')
def library_categories(user=Depends(current_user)): return {'categories':sorted([x for x in get_db().learning_library.distinct('category') if x])}

@router.get('/media/{file_id}')
def stream_media(file_id:str):
    doc=_find_media(file_id)
    if not doc or not doc.get('storage_key'): raise HTTPException(404,'Media not found')
    try: return RedirectResponse(_signed_url(doc['storage_key'],False,doc.get('filename','download')),status_code=307)
    except Exception as exc: raise HTTPException(503,f'Media storage unavailable: {exc}')

@router.get('/media/{file_id}/download')
def download_media(file_id:str):
    doc=_find_media(file_id)
    if not doc or not doc.get('storage_key'): raise HTTPException(404,'Media not found')
    try: return RedirectResponse(_signed_url(doc['storage_key'],True,doc.get('filename','download')),status_code=307)
    except Exception as exc: raise HTTPException(503,f'Media storage unavailable: {exc}')
