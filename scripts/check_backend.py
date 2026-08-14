import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app
from app.core.config import get_settings

print("Application import: OK")
print("Routes:", len(app.routes))
print("Database:", get_settings().mongodb_db)
