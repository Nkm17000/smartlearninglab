from app.repositories.user_repository import UserRepository
from app.core.security import hash_password, verify_password, create_access_token

class AuthService:
    def __init__(self):
        self.repository = UserRepository()

    def register(self, name, email, password):
        email = email.lower()
        if self.repository.find_by_email(email):
            raise ValueError("Email already registered")
        user = {
            "name": name,
            "email": email,
            "password_hash": hash_password(password),
            "role": "STUDENT",
            "profile_image": None,
            "is_active": True
        }
        result = self.repository.insert(user)
        return {
            "access_token": create_access_token(str(result.inserted_id), "STUDENT"),
            "token_type": "bearer",
            "user_id": str(result.inserted_id),
            "email": email,
            "role": "STUDENT"
        }

    def login(self, email, password):
        user = self.repository.find_by_email(email.lower())
        if not user or not verify_password(password, user["password_hash"]):
            raise ValueError("Invalid email or password")
        return {
            "access_token": create_access_token(str(user["_id"]), user["role"]),
            "token_type": "bearer",
            "user_id": str(user["_id"]),
            "email": user["email"],
            "role": user["role"]
        }
