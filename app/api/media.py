from datetime import datetime, timezone
import mimetypes
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from gridfs import GridFSBucket
from bson import ObjectId

from app.core.security import current_user, admin_user
from app.db.mongo import get_db

router = APIRouter(prefix='/api/v1', tags=['Media & Library'])

COURSE_CATEGORIES = [
    'SSC', 'Banking', 'UPSC', 'English Spoken', 'Railway',
    'Teaching', 'Defence', 'State Exams', 'Computer', 'General', 'Other'
]
RESOURCE_TYPES = {'video', 'audio', 'pdf', 'document', 'image', 'link', 'other'}
MAX_UPLOAD_MB = 250


def now():
    return datetime.now(timezone.utc)


def uid(user):
    return str(user['_id'])


def clean(v):
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items() if k != 'password_hash'}
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, ObjectId):
        return str(v)
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    return v


def find(collection, item_id):
    db = get_db()
    x = db[collection].find_one({'_id': item_id})
    if x:
        return x
    try:
        if ObjectId.is_valid(item_id):
            return db[collection].find_one({'_id': ObjectId(item_id)})
    except Exception:
        pass
    return None


def infer_type(filename: str, content_type: str = ''):
    ext = os.path.splitext(filename.lower())[1]
    if content_type == 'application/pdf' or ext == '.pdf':
        return 'pdf'
    if content_type.startswith('video/') or ext in {'.mp4', '.webm', '.mov', '.m4v'}:
        return 'video'
    if content_type.startswith('audio/') or ext in {'.mp3', '.wav', '.m4a', '.aac', '.ogg'}:
        return 'audio'
    if content_type.startswith('image/') or ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
        return 'image'
    if ext in {'.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.txt'}:
        return 'document'
    return 'other'


def upload_file(upload: UploadFile, metadata: dict):
    filename = os.path.basename(upload.filename or f'upload-{uuid.uuid4().hex}')
    content_type = upload.content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    resource_type = metadata.get('type') or infer_type(filename, content_type)
    if resource_type not in RESOURCE_TYPES:
        resource_type = 'other'

    bucket = GridFSBucket(get_db(), bucket_name='sll_media')
    file_id = bucket.upload_from_stream(
        filename,
        upload.file,
        metadata={
            **metadata,
            'content_type': content_type,
            'resource_type': resource_type,
            'uploaded_at': now(),
        }
    )
    return str(file_id), filename, content_type, resource_type


def public_url(file_id: str):
    return f'/api/v1/media/{file_id}'


@router.get('/admin/course-categories')
def admin_course_categories(user=Depends(admin_user)):
    return {'categories': COURSE_CATEGORIES}


@router.post('/admin/courses/{course_id}/resources/upload')
def upload_course_resource(
    course_id: str,
    file: UploadFile = File(...),
    title: str = '',
    resource_type: str = '',
    description: str = '',
    user=Depends(admin_user),
):
    course = find('courses', course_id)
    if not course:
        raise HTTPException(404, 'Course not found')
    if not file.filename:
        raise HTTPException(422, 'File is required')
    if resource_type and resource_type not in RESOURCE_TYPES:
        raise HTTPException(422, 'Unsupported resource type')

    file_id, filename, content_type, inferred = upload_file(file, {
        'owner_type': 'course',
        'course_id': course_id,
        'uploaded_by': uid(user),
        'type': resource_type or None,
    })
    kind = resource_type or inferred
    doc = {
        '_id': uuid.uuid4().hex,
        'course_id': course_id,
        'title': title.strip() or filename,
        'description': description.strip(),
        'url': public_url(file_id),
        'media_id': file_id,
        'filename': filename,
        'content_type': content_type,
        'type': kind,
        'source': 'upload',
        'order': get_db().course_resources.count_documents({'course_id': course_id}) + 1,
        'created_at': now(),
        'created_by': uid(user),
    }
    get_db().course_resources.insert_one(doc)
    get_db().courses.update_one({'_id': course.get('_id')}, {'$inc': {f'{kind}_count': 1}})
    return clean(doc)


@router.post('/admin/courses/{course_id}/resources')
def create_course_resource(course_id: str, data: dict, user=Depends(admin_user)):
    course = find('courses', course_id)
    if not course:
        raise HTTPException(404, 'Course not found')
    title = str(data.get('title', '')).strip()
    url = str(data.get('url', '')).strip()
    kind = str(data.get('type', 'link')).lower()
    if not title or not url:
        raise HTTPException(422, 'title and url are required')
    if kind not in RESOURCE_TYPES:
        raise HTTPException(422, 'Unsupported resource type')
    doc = {
        '_id': uuid.uuid4().hex,
        'course_id': course_id,
        'title': title,
        'description': str(data.get('description', '')).strip(),
        'url': url,
        'type': kind,
        'source': 'url',
        'order': get_db().course_resources.count_documents({'course_id': course_id}) + 1,
        'created_at': now(),
        'created_by': uid(user),
    }
    get_db().course_resources.insert_one(doc)
    return clean(doc)


@router.get('/admin/courses/{course_id}/resources')
def admin_course_resources(course_id: str, user=Depends(admin_user)):
    if not find('courses', course_id):
        raise HTTPException(404, 'Course not found')
    return [clean(x) for x in get_db().course_resources.find({'course_id': course_id}).sort('order', 1)]


@router.delete('/admin/courses/{course_id}/resources/{resource_id}')
def delete_course_resource(course_id: str, resource_id: str, user=Depends(admin_user)):
    db = get_db()
    resource = db.course_resources.find_one({'_id': resource_id, 'course_id': course_id})
    if not resource:
        raise HTTPException(404, 'Course resource not found')
    if resource.get('media_id'):
        try:
            GridFSBucket(db, bucket_name='sll_media').delete(ObjectId(resource['media_id']))
        except Exception:
            pass
    db.course_resources.delete_one({'_id': resource_id})
    kind = resource.get('type')
    if kind in RESOURCE_TYPES:
        db.courses.update_one({'_id': find('courses', course_id)['_id']}, {'$inc': {f'{kind}_count': -1}})
    return {'message': 'Course resource deleted'}


@router.post('/admin/lessons/{lesson_id}/resources/upload')
def upload_lesson_resource(
    lesson_id: str,
    file: UploadFile = File(...),
    title: str = '',
    resource_type: str = '',
    description: str = '',
    user=Depends(admin_user),
):
    lesson = find('lessons', lesson_id)
    if not lesson:
        raise HTTPException(404, 'Lesson not found')
    if not file.filename:
        raise HTTPException(422, 'File is required')
    if resource_type and resource_type not in RESOURCE_TYPES:
        raise HTTPException(422, 'Unsupported resource type')
    file_id, filename, content_type, inferred = upload_file(file, {
        'owner_type': 'lesson',
        'lesson_id': lesson_id,
        'course_id': lesson.get('course_id'),
        'uploaded_by': uid(user),
        'type': resource_type or None,
    })
    kind = resource_type or inferred
    doc = {
        '_id': uuid.uuid4().hex,
        'lesson_id': lesson_id,
        'course_id': lesson.get('course_id'),
        'title': title.strip() or filename,
        'description': description.strip(),
        'url': public_url(file_id),
        'media_id': file_id,
        'filename': filename,
        'content_type': content_type,
        'type': kind,
        'source': 'upload',
        'order': get_db().lesson_resources.count_documents({'lesson_id': lesson_id}) + 1,
        'created_at': now(),
        'created_by': uid(user),
    }
    get_db().lesson_resources.insert_one(doc)
    return clean(doc)


@router.post('/admin/library/upload')
def upload_library_file(
    file: UploadFile = File(...),
    title: str = '',
    category: str = 'General',
    description: str = '',
    tags: str = '',
    user=Depends(admin_user),
):
    if not file.filename:
        raise HTTPException(422, 'File is required')
    file_id, filename, content_type, inferred = upload_file(file, {
        'owner_type': 'library',
        'uploaded_by': uid(user),
        'category': category or 'General',
    })
    doc = {
        '_id': uuid.uuid4().hex,
        'title': title.strip() or filename,
        'description': description.strip(),
        'category': category.strip() or 'General',
        'tags': [x.strip() for x in tags.split(',') if x.strip()],
        'filename': filename,
        'content_type': content_type,
        'type': inferred,
        'media_id': file_id,
        'url': public_url(file_id),
        'is_published': True,
        'created_at': now(),
        'created_by': uid(user),
    }
    get_db().learning_library.insert_one(doc)
    return clean(doc)


@router.post('/admin/library')
def create_library_link(data: dict, user=Depends(admin_user)):
    title = str(data.get('title', '')).strip()
    url = str(data.get('url', '')).strip()
    if not title or not url:
        raise HTTPException(422, 'title and url are required')
    kind = str(data.get('type', 'pdf')).lower()
    if kind not in RESOURCE_TYPES:
        raise HTTPException(422, 'Unsupported resource type')
    doc = {
        '_id': uuid.uuid4().hex,
        'title': title,
        'description': str(data.get('description', '')).strip(),
        'category': str(data.get('category', 'General')).strip() or 'General',
        'tags': data.get('tags', []) or [],
        'type': kind,
        'url': url,
        'source': 'url',
        'is_published': True,
        'created_at': now(),
        'created_by': uid(user),
    }
    get_db().learning_library.insert_one(doc)
    return clean(doc)


@router.get('/admin/library')
def admin_library(user=Depends(admin_user)):
    return [clean(x) for x in get_db().learning_library.find({}).sort('created_at', -1)]


@router.delete('/admin/library/{item_id}')
def delete_library(item_id: str, user=Depends(admin_user)):
    db = get_db()
    item = db.learning_library.find_one({'_id': item_id})
    if not item:
        raise HTTPException(404, 'Library item not found')
    if item.get('media_id'):
        try:
            GridFSBucket(db, bucket_name='sll_media').delete(ObjectId(item['media_id']))
        except Exception:
            pass
    db.learning_library.delete_one({'_id': item_id})
    return {'message': 'Library item deleted'}


@router.get('/library')
def student_library(category: str | None = None, user=Depends(current_user)):
    q = {'is_published': True}
    if category:
        q['category'] = category
    return [clean(x) for x in get_db().learning_library.find(q).sort('created_at', -1)]


@router.get('/library/categories')
def library_categories(user=Depends(current_user)):
    return {'categories': sorted([x for x in get_db().learning_library.distinct('category') if x])}


@router.get('/media/{file_id}')
def stream_media(file_id: str):
    try:
        oid = ObjectId(file_id)
    except Exception:
        raise HTTPException(404, 'Media not found')
    bucket = GridFSBucket(get_db(), bucket_name='sll_media')
    try:
        stream = bucket.open_download_stream(oid)
    except Exception:
        raise HTTPException(404, 'Media not found')
    content_type = (stream.metadata or {}).get('content_type', 'application/octet-stream')
    filename = stream.filename or 'download'

    def iterator():
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            yield chunk

    return StreamingResponse(
        iterator(),
        media_type=content_type,
        headers={'Content-Disposition': f'inline; filename="{filename.replace(chr(34), "")}"'},
    )


@router.get('/media/{file_id}/download')
def download_media(file_id: str):
    """Download a library/course/lesson media file."""
    try:
        oid = ObjectId(file_id)
    except Exception:
        raise HTTPException(404, 'Media not found')
    bucket = GridFSBucket(get_db(), bucket_name='sll_media')
    try:
        stream = bucket.open_download_stream(oid)
    except Exception:
        raise HTTPException(404, 'Media not found')

    content_type = (stream.metadata or {}).get('content_type', 'application/octet-stream')
    filename = (stream.filename or 'download').replace('"', '')

    def iterator():
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            yield chunk

    return StreamingResponse(
        iterator(),
        media_type=content_type,
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-store',
        },
    )
