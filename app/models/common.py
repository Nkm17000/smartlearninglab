from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class MongoModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class IdResponse(BaseModel):
    id: str


class PaginatedResponse(BaseModel):
    items: list[Any]
    page: int
    limit: int
    total: int
    pages: int


class MessageResponse(BaseModel):
    message: str
