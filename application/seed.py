from . import db
from .models import User


def seed_default_users():
    default_users = [
        {"username": "alex", "password": "pass123"},
        {"username": "blake", "password": "pass123"},
        {"username": "casey", "password": "pass123"},
    ]

    for user_data in default_users:
        existing = User.query.filter_by(username=user_data["username"]).first()
        if existing:
            continue

        user = User(username=user_data["username"])
        user.set_password(user_data["password"])
        db.session.add(user)

    db.session.commit()
