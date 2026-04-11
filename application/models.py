from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from application import db, login_manager


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    tasks = db.relationship("Task", backref="user", lazy=True, cascade="all, delete-orphan")
    focuses = db.relationship(
        "CurrentFocus", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    achievements = db.relationship(
        "Achievement", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    fines = db.relationship(
        "SlackingJarEntry", foreign_keys="SlackingJarEntry.user_id", backref="target_user", lazy=True
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class Task(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="todo")
    priority = db.Column(db.String(20), nullable=False, default="medium")
    deadline = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class CurrentFocus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status_note = db.Column(db.String(160), nullable=True)
    target_date = db.Column(db.Date, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BacklogItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(40), nullable=False, default="shared")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by])


class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date_achieved = db.Column(db.Date, default=date.today, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SlackingJarEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=1.0)
    is_paid = db.Column(db.Boolean, default=False, nullable=False)
    issued_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date_issued = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    issuer = db.relationship("User", foreign_keys=[issued_by])
