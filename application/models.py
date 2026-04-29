from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from application import login_manager
from application.supabase_client import sb


class User(UserMixin):
    def __init__(self, id, name, email, password_hash=None, created_at=None):
        self.id = int(id)
        self.name = name
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at

    def get_id(self) -> str:
        return str(self.id)

    @classmethod
    def from_row(cls, row: dict) -> "User":
        return cls(
            id=row["id"],
            name=row.get("name"),
            email=row.get("email"),
            password_hash=row.get("password_hash"),
            created_at=row.get("created_at"),
        )

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash or "", password)

    @staticmethod
    def hash_password(password: str) -> str:
        return generate_password_hash(password)


@login_manager.user_loader
def load_user(user_id: str):
    res = sb().table("users").select("*").eq("id", int(user_id)).limit(1).execute()
    if res.data:
        return User.from_row(res.data[0])
    return None
