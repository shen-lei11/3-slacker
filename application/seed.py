from datetime import date, timedelta

from application import create_app, db
from application.models import Achievement, BacklogItem, CurrentFocus, SlackingJarEntry, Task, User


def seed() -> None:
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        users = [
            User(name="Alex Carter", email="alex@example.com"),
            User(name="Sarah Jenkins", email="sarah@example.com"),
            User(name="Mark Davies", email="mark@example.com"),
        ]
        for user in users:
            user.set_password("password123")
        db.session.add_all(users)
        db.session.flush()

        db.session.add_all(
            [
                Task(title="Finish API Integration", description="Backend endpoints", status="doing", priority="high", deadline=date.today() + timedelta(days=1), user_id=users[0].id),
                Task(title="Design Marketing Assets", description="Launch banner set", status="todo", priority="high", deadline=date.today(), user_id=users[1].id),
                Task(title="Fix Navigation Bug", description="Navbar overflow", status="todo", priority="medium", deadline=date.today() + timedelta(days=2), user_id=users[2].id),
                Task(title="Prepare Sprint Demo", description="Demo checklist", status="done", priority="low", deadline=date.today() - timedelta(days=1), user_id=users[0].id),
            ]
        )

        db.session.add_all(
            [
                CurrentFocus(user_id=users[0].id, title="Auth hardening", description="Improve login/session handling", status_note="In progress", target_date=date.today() + timedelta(days=2)),
                CurrentFocus(user_id=users[1].id, title="Landing page visuals", description="Hero and CTA refresh", status_note="Needs review", target_date=date.today() + timedelta(days=3)),
                CurrentFocus(user_id=users[2].id, title="Performance pass", description="Query audit", status_note="Blocked by data", target_date=date.today() + timedelta(days=4)),
            ]
        )

        db.session.add_all(
            [
                BacklogItem(title="Redesign Landing Page Hero", description="Improve conversion", category="shared", created_by=users[0].id),
                BacklogItem(title="Learn GraphQL Basics", description="Build sample API", category="personal", created_by=users[1].id),
                BacklogItem(title="Organize Team Offsite", description="After launch", category="someday", created_by=users[2].id),
            ]
        )

        db.session.add_all(
            [
                Achievement(title="Launched MVP v1.0", description="Core flow is live", user_id=users[0].id, date_achieved=date.today()),
                Achievement(title="Closed Sprint Goal Early", description="Delivered 2 days ahead", user_id=users[1].id, date_achieved=date.today() - timedelta(days=1)),
            ]
        )

        db.session.add_all(
            [
                SlackingJarEntry(user_id=users[2].id, issued_by=users[0].id, reason="Late to standup", amount=5, is_paid=False),
                SlackingJarEntry(user_id=users[0].id, issued_by=users[1].id, reason="Missed review deadline", amount=10, is_paid=False),
                SlackingJarEntry(user_id=users[1].id, issued_by=users[2].id, reason="Phone during focus session", amount=3, is_paid=True),
            ]
        )

        db.session.commit()
        print("Seed complete. Users: alex@example.com, sarah@example.com, mark@example.com | password: password123")


if __name__ == "__main__":
    seed()
