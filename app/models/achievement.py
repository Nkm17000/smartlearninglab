from typing import Any, Dict
from pydantic import BaseModel

class AchievementModel(BaseModel):
    name: str
    description: str
    icon: str | None = None
    criteria: Dict[str, Any] = {}
