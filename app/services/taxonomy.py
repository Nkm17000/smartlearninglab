import re

EXAM_CATEGORIES = [
    'SSC', 'Railway', 'Banking', 'UPSC', 'Computer', 'Teaching',
    'Defence', 'State Exams', 'General', 'English Spoken', 'Other'
]

SUBJECTS = [
    'English', 'Hindi', 'Math', 'Reasoning', 'General Awareness', 'Current Affairs',
    'Science', 'Physics', 'Chemistry', 'Biology', 'Computer', 'Java', 'Python',
    'PHP', 'SQL', 'DBMS', 'Operating Systems', 'Networking', 'Web Development',
    'Spring Boot', 'Microservices', 'Aptitude', 'Other'
]

_ALIAS = {x.casefold(): x for x in EXAM_CATEGORIES}
_SUBJECT_ALIAS = {x.casefold(): x for x in SUBJECTS}


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw = value
    else:
        text = str(value).strip()
        if not text:
            return []
        # Accept comma/pipe-separated values from legacy forms and bulk uploads.
        raw = re.split(r'[,|]', text)
    out = []
    for item in raw:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def normalize_categories(value, default='General'):
    values = _as_list(value) or [default]
    result = []
    for value in values:
        canonical = _ALIAS.get(value.casefold(), value.title() if value.casefold() not in _ALIAS else _ALIAS[value.casefold()])
        if canonical not in result:
            result.append(canonical)
    return result[:20]


def normalize_subject(value, default='General'):
    text = str(value or '').strip()
    if not text:
        return default
    return _SUBJECT_ALIAS.get(text.casefold(), text)


def normalize_category_document(doc):
    """Return a backward-compatible document with canonical category array."""
    out = dict(doc or {})
    categories = normalize_categories(out.get('categories', out.get('category')))
    out['categories'] = categories
    # Keep category for old UI/API consumers.
    out['category'] = categories[0] if categories else 'General'
    out['subject'] = normalize_subject(out.get('subject'))
    return out


def quiz_group_key(title, subject):
    """Stable readable identity shared by copies of the same subject quiz across exams."""
    text = f"{normalize_subject(subject)}|{str(title or '').strip()}"
    return re.sub(r'\s+', ' ', text).strip().casefold()


def category_query(field, category):
    """Mongo query fragment supporting new arrays and legacy scalar category."""
    if not category or str(category).casefold() == 'all':
        return None
    value = str(category).strip()
    prefix = f'{field}.' if field else ''
    return {'$or': [{f'{prefix}categories': value}, {f'{prefix}category': value}, {f'{prefix}category': {'$regex': f'^{re.escape(value)}$', '$options': 'i'}}]}
