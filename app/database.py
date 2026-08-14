from pymongo import MongoClient
from app.config import settings


client = MongoClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=8000,
    connectTimeoutMS=8000,
    socketTimeoutMS=10000,
    maxPoolSize=20,
)

db = client[settings.mongodb_database]


def ping_database():
    client.admin.command("ping")
    return True


def collection(name: str):
    return db[name]


def close_database():
    client.close()