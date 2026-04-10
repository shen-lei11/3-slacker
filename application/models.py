from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    tasks = db.relationship("Task", backref="owner", lazy=True, cascade="all, delete-orphan")
    current_focus_entries = db.relationship(
        "CurrentFocus",
        backref="owner",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="desc(CurrentFocus.updated_at)"
    )
    achievements = db.relationship(
        "Achievement",
        backref="owner",
        lazy=True,
        cascade="all, delete-orphan"
    )
    slacking_entries = db.relationship(
        "SlackingJarEntry",
        backref="target_user",
        lazy=True,
        cascade="all, delete-orphan",
        foreign_keys="SlackingJarEntry.user_id"
    )
    fines_issued = db.relationship(
        "SlackingJarEntry",
        backref="issuer",
        lazy=True,
        foreign_keys="SlackingJarEntry.issued_by"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="To Do")
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    deadline = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )


class CurrentFocus(db.Model):
    __tablename__ = "current_focus"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status_note = db.Column(db.String(255), nullable=True)
    target_date = db.Column(db.Date, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )


class BacklogItem(db.Model):
    __tablename__ = "backlog_items"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(40), nullable=False, default="Other")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", backref="backlog_items")


class Achievement(db.Model):
    __tablename__ = "achievements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date_achieved = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SlackingJarEntry(db.Model):
    __tablename__ = "slacking_jar_entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=1.00)
    is_paid = db.Column(db.Boolean, nullable=False, default=False)
    issued_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date_issued = db.Column(db.Date, nullable=False)
