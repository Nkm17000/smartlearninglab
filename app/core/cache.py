"""Small in-process TTL cache for hot, read-heavy API responses.

Designed for Render/FastAPI: no external dependency and bounded size. Cache is
per process, so it is intentionally used only for short-lived acceleration;
MongoDB remains the source of truth.
"""
from __future__ import annotations

from copy import deepcopy
from threading import RLock
from time import monotonic


class TTLCache:
    def __init__(self, max_items: int = 512):
        self.max_items = max_items
        self._data: dict[str, tuple[float, object]] = {}
        self._lock = RLock()

    def get(self, key: str):
        now = monotonic()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires, value = item
            if expires <= now:
                self._data.pop(key, None)
                return None
            return deepcopy(value)

    def set(self, key: str, value, ttl_seconds: int):
        with self._lock:
            if len(self._data) >= self.max_items and key not in self._data:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                self._data.pop(oldest, None)
            self._data[key] = (monotonic() + ttl_seconds, deepcopy(value))

    def delete_prefix(self, prefix: str):
        with self._lock:
            for key in list(self._data):
                if key.startswith(prefix):
                    self._data.pop(key, None)

    def clear(self):
        with self._lock:
            self._data.clear()


cache = TTLCache(max_items=1024)

# Cache policy. Short user data TTLs avoid stale learning progress while
# catalogue data gets longer TTLs because it changes much less frequently.
TTL_DASHBOARD = 30
TTL_COURSES = 60
TTL_CATEGORIES = 900
TTL_FEATURED = 300
TTL_COURSE_OVERVIEW = 300
TTL_QUIZZES = 60
TTL_PERSONALIZED_PATH = 120
TTL_ANALYTICS = 60
TTL_ADVANCED_ANALYTICS = 300
TTL_LEADERBOARD = 120
TTL_BOOKMARKS = 30
TTL_CERTIFICATES = 300
TTL_NOTIFICATIONS = 15
TTL_CONVERSATIONS = 30
TTL_MESSAGES = 30
TTL_FLASHCARDS = 60
TTL_BADGES = 300
TTL_LIBRARY = 300
TTL_LIBRARY_CATEGORIES = 900
TTL_RESULTS = 30
TTL_PROGRESS = 15
TTL_NOTES = 30
TTL_ENROLLMENTS = 60


def invalidate_user(user_id: str):
    """Invalidate all short-lived user caches after a mutation."""
    prefixes = (
        f"dashboard:{user_id}",
        f"home:{user_id}",
        f"progress:{user_id}",
        f"results:{user_id}",
        f"personalized:{user_id}",
        f"analytics:{user_id}",
        f"bookmarks:{user_id}",
        f"certificates:{user_id}",
        f"notifications:{user_id}",
        f"conversations:{user_id}",
        f"flashcards:{user_id}",
        f"badges:{user_id}",
    )
    for prefix in prefixes:
        cache.delete_prefix(prefix)
