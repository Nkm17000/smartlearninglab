from pydantic import BaseModel

class AchievementCreate(BaseModel):
    name: str
    description: str
    icon: str | None = None
    criteria: dict = {}
