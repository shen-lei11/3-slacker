from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from . import db
from .forms import (
    AchievementForm,
    BacklogForm,
    CurrentFocusForm,
    SlackingJarForm,
    TaskForm,
)
from .models import Achievement, BacklogItem, CurrentFocus, SlackingJarEntry, Task, User


main_bp = Blueprint("main", __name__)
TASK_STATUSES = ["To Do", "In Progress", "Done"]


@main_bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    users = User.query.order_by(User.username.asc()).all()
    summaries = []

    for user in users:
        latest_focus = (
            CurrentFocus.query.filter_by(user_id=user.id)
            .order_by(CurrentFocus.updated_at.desc())
            .first()
        )
        counts = {status: 0 for status in TASK_STATUSES}
        task_counts = (
            db.session.query(Task.status, func.count(Task.id))
            .filter(Task.user_id == user.id)
            .group_by(Task.status)
            .all()
        )
        for status, count in task_counts:
            counts[status] = count

        user_unpaid = (
            db.session.query(func.coalesce(func.sum(SlackingJarEntry.amount), 0))
            .filter(SlackingJarEntry.user_id == user.id, SlackingJarEntry.is_paid.is_(False))
            .scalar()
            or Decimal("0")
        )

        summaries.append(
            {
                "user": user,
                "latest_focus": latest_focus,
                "counts": counts,
                "unpaid_total": user_unpaid,
            }
        )

    latest_achievements = Achievement.query.order_by(Achievement.created_at.desc()).limit(5).all()
    overall_unpaid = (
        db.session.query(func.coalesce(func.sum(SlackingJarEntry.amount), 0))
        .filter(SlackingJarEntry.is_paid.is_(False))
        .scalar()
        or Decimal("0")
    )

    return render_template(
        "dashboard.html",
        summaries=summaries,
        latest_achievements=latest_achievements,
        overall_unpaid=overall_unpaid,
        unpaid_total=overall_unpaid,
    )


@main_bp.route("/board")
@login_required
def board():
    status_filter = request.args.get("status", "all")

    tasks_query = Task.query.filter_by(user_id=current_user.id)
    if status_filter in TASK_STATUSES:
        tasks_query = tasks_query.filter_by(status=status_filter)

    tasks = tasks_query.order_by(Task.created_at.desc()).all()
    grouped_tasks = {status: [] for status in TASK_STATUSES}
    for task in tasks:
        grouped_tasks[task.status].append(task)

    return render_template(
        "board.html",
        grouped_tasks=grouped_tasks,
        status_filter=status_filter,
        statuses=TASK_STATUSES,
    )


@main_bp.route("/tasks/create", methods=["GET", "POST"])
@login_required
def create_task():
    form = TaskForm()
    if form.validate_on_submit():
        task = Task(
            title=form.title.data.strip(),
            description=form.description.data,
            status=form.status.data,
            priority=form.priority.data,
            deadline=form.deadline.data,
            user_id=current_user.id,
        )
        db.session.add(task)
        db.session.commit()
        flash("Task created.", "success")
        return redirect(url_for("main.board"))
    return render_template("task_form.html", form=form, mode="Create")


@main_bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first()
    if not task:
        flash("Task not found.", "warning")
        return redirect(url_for("main.board"))

    form = TaskForm(obj=task)
    if form.validate_on_submit():
        task.title = form.title.data.strip()
        task.description = form.description.data
        task.status = form.status.data
        task.priority = form.priority.data
        task.deadline = form.deadline.data
        db.session.commit()
        flash("Task updated.", "success")
        return redirect(url_for("main.board"))

    return render_template("task_form.html", form=form, mode="Edit")


@main_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first()
    if not task:
        flash("Task not found.", "warning")
        return redirect(url_for("main.board"))

    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for("main.board"))


@main_bp.route("/tasks/<int:task_id>/status/<string:new_status>", methods=["POST"])
@login_required
def change_task_status(task_id, new_status):
    if new_status not in TASK_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("main.board"))

    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first()
    if not task:
        flash("Task not found.", "warning")
        return redirect(url_for("main.board"))

    task.status = new_status
    db.session.commit()
    flash("Task status updated.", "success")
    return redirect(url_for("main.board"))


@main_bp.route("/tracker")
@login_required
def tracker():
    users = User.query.order_by(User.username.asc()).all()
    latest_entries = {}
    for user in users:
        latest_entries[user.id] = (
            CurrentFocus.query.filter_by(user_id=user.id)
            .order_by(CurrentFocus.updated_at.desc())
            .first()
        )

    existing = (
        CurrentFocus.query.filter_by(user_id=current_user.id)
        .order_by(CurrentFocus.updated_at.desc())
        .first()
    )
    form = CurrentFocusForm(obj=existing)

    return render_template(
        "tracker.html",
        users=users,
        latest_entries=latest_entries,
        form=form,
        existing=existing,
    )


@main_bp.route("/tracker/create", methods=["POST"])
@main_bp.route("/tracker/edit", methods=["POST"])
@login_required
def save_tracker_entry():
    existing = (
        CurrentFocus.query.filter_by(user_id=current_user.id)
        .order_by(CurrentFocus.updated_at.desc())
        .first()
    )

    form = CurrentFocusForm()
    if not form.validate_on_submit():
        flash("Please fix the errors in your focus update.", "danger")
        return redirect(url_for("main.tracker"))

    if existing:
        existing.title = form.title.data.strip()
        existing.description = form.description.data
        existing.status_note = form.status_note.data
        existing.target_date = form.target_date.data
        flash("Current focus updated.", "success")
    else:
        entry = CurrentFocus(
            user_id=current_user.id,
            title=form.title.data.strip(),
            description=form.description.data,
            status_note=form.status_note.data,
            target_date=form.target_date.data,
        )
        db.session.add(entry)
        flash("Current focus added.", "success")

    db.session.commit()
    return redirect(url_for("main.tracker"))


@main_bp.route("/backlog")
@login_required
def backlog():
    items = BacklogItem.query.order_by(BacklogItem.created_at.desc()).all()
    return render_template("backlog.html", items=items)


@main_bp.route("/backlog/create", methods=["GET", "POST"])
@login_required
def create_backlog_item():
    form = BacklogForm()
    if form.validate_on_submit():
        item = BacklogItem(
            title=form.title.data.strip(),
            description=form.description.data,
            category=form.category.data,
            created_by=current_user.id,
        )
        db.session.add(item)
        db.session.commit()
        flash("Backlog item created.", "success")
        return redirect(url_for("main.backlog"))

    return render_template("backlog_form.html", form=form, mode="Create")


@main_bp.route("/backlog/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_backlog_item(item_id):
    item = BacklogItem.query.get(item_id)
    if not item:
        flash("Backlog item not found.", "warning")
        return redirect(url_for("main.backlog"))

    form = BacklogForm(obj=item)
    if form.validate_on_submit():
        item.title = form.title.data.strip()
        item.description = form.description.data
        item.category = form.category.data
        db.session.commit()
        flash("Backlog item updated.", "success")
        return redirect(url_for("main.backlog"))

    return render_template("backlog_form.html", form=form, mode="Edit")


@main_bp.route("/backlog/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_backlog_item(item_id):
    item = BacklogItem.query.get(item_id)
    if not item:
        flash("Backlog item not found.", "warning")
        return redirect(url_for("main.backlog"))

    db.session.delete(item)
    db.session.commit()
    flash("Backlog item deleted.", "info")
    return redirect(url_for("main.backlog"))


@main_bp.route("/achievements")
@login_required
def achievements():
    entries = Achievement.query.order_by(Achievement.date_achieved.desc(), Achievement.created_at.desc()).all()
    return render_template("achievements.html", entries=entries)


@main_bp.route("/achievements/create", methods=["GET", "POST"])
@login_required
def create_achievement():
    form = AchievementForm()
    if form.validate_on_submit():
        entry = Achievement(
            title=form.title.data.strip(),
            description=form.description.data,
            user_id=current_user.id,
            date_achieved=form.date_achieved.data,
        )
        db.session.add(entry)
        db.session.commit()
        flash("Achievement posted.", "success")
        return redirect(url_for("main.achievements"))

    return render_template("achievement_form.html", form=form, mode="Create")


@main_bp.route("/achievements/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit_achievement(entry_id):
    entry = Achievement.query.get(entry_id)
    if not entry:
        flash("Achievement not found.", "warning")
        return redirect(url_for("main.achievements"))

    if entry.user_id != current_user.id:
        flash("You can only edit your own achievement posts.", "danger")
        return redirect(url_for("main.achievements"))

    form = AchievementForm(obj=entry)
    if form.validate_on_submit():
        entry.title = form.title.data.strip()
        entry.description = form.description.data
        entry.date_achieved = form.date_achieved.data
        db.session.commit()
        flash("Achievement updated.", "success")
        return redirect(url_for("main.achievements"))

    return render_template("achievement_form.html", form=form, mode="Edit")


@main_bp.route("/achievements/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_achievement(entry_id):
    entry = Achievement.query.get(entry_id)
    if not entry:
        flash("Achievement not found.", "warning")
        return redirect(url_for("main.achievements"))

    if entry.user_id != current_user.id:
        flash("You can only delete your own achievement posts.", "danger")
        return redirect(url_for("main.achievements"))

    db.session.delete(entry)
    db.session.commit()
    flash("Achievement removed.", "info")
    return redirect(url_for("main.achievements"))


def _populate_jar_form_choices(form):
    users = User.query.order_by(User.username.asc()).all()
    choices = [(user.id, user.username) for user in users]
    form.user_id.choices = choices
    form.issued_by.choices = choices


@main_bp.route("/jar")
@login_required
def jar():
    user_filter = request.args.get("user", type=int)
    paid_filter = request.args.get("paid", "all")

    query = SlackingJarEntry.query

    if user_filter:
        query = query.filter_by(user_id=user_filter)
    if paid_filter == "paid":
        query = query.filter(SlackingJarEntry.is_paid.is_(True))
    elif paid_filter == "unpaid":
        query = query.filter(SlackingJarEntry.is_paid.is_(False))

    entries = query.order_by(SlackingJarEntry.date_issued.desc()).all()

    overall_unpaid = (
        db.session.query(func.coalesce(func.sum(SlackingJarEntry.amount), 0))
        .filter(SlackingJarEntry.is_paid.is_(False))
        .scalar()
        or Decimal("0")
    )

    users = User.query.order_by(User.username.asc()).all()
    unpaid_per_user = []
    for user in users:
        user_total = (
            db.session.query(func.coalesce(func.sum(SlackingJarEntry.amount), 0))
            .filter(SlackingJarEntry.user_id == user.id, SlackingJarEntry.is_paid.is_(False))
            .scalar()
            or Decimal("0")
        )
        unpaid_per_user.append((user, user_total))

    return render_template(
        "jar.html",
        entries=entries,
        users=users,
        user_filter=user_filter,
        paid_filter=paid_filter,
        overall_unpaid=overall_unpaid,
        unpaid_per_user=unpaid_per_user,
    )


@main_bp.route("/jar/create", methods=["GET", "POST"])
@login_required
def create_jar_entry():
    form = SlackingJarForm()
    _populate_jar_form_choices(form)

    if form.validate_on_submit():
        entry = SlackingJarEntry(
            user_id=form.user_id.data,
            reason=form.reason.data.strip(),
            amount=form.amount.data,
            is_paid=form.is_paid.data,
            issued_by=form.issued_by.data,
            date_issued=form.date_issued.data,
        )
        db.session.add(entry)
        db.session.commit()
        flash("Slacking fine recorded.", "success")
        return redirect(url_for("main.jar"))

    return render_template("jar_form.html", form=form, mode="Create")


@main_bp.route("/jar/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit_jar_entry(entry_id):
    entry = SlackingJarEntry.query.get(entry_id)
    if not entry:
        flash("Fine record not found.", "warning")
        return redirect(url_for("main.jar"))

    form = SlackingJarForm(obj=entry)
    _populate_jar_form_choices(form)

    if form.validate_on_submit():
        entry.user_id = form.user_id.data
        entry.reason = form.reason.data.strip()
        entry.amount = form.amount.data
        entry.is_paid = form.is_paid.data
        entry.issued_by = form.issued_by.data
        entry.date_issued = form.date_issued.data
        db.session.commit()
        flash("Fine record updated.", "success")
        return redirect(url_for("main.jar"))

    return render_template("jar_form.html", form=form, mode="Edit")


@main_bp.route("/jar/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_jar_entry(entry_id):
    entry = SlackingJarEntry.query.get(entry_id)
    if not entry:
        flash("Fine record not found.", "warning")
        return redirect(url_for("main.jar"))

    db.session.delete(entry)
    db.session.commit()
    flash("Fine record deleted.", "info")
    return redirect(url_for("main.jar"))


@main_bp.route("/jar/<int:entry_id>/toggle-paid", methods=["POST"])
@login_required
def toggle_paid(entry_id):
    entry = SlackingJarEntry.query.get(entry_id)
    if not entry:
        flash("Fine record not found.", "warning")
        return redirect(url_for("main.jar"))

    entry.is_paid = not entry.is_paid
    db.session.commit()
    flash("Payment status toggled.", "success")
    return redirect(url_for("main.jar"))
