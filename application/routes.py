from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from application import db
from application.forms import (
    AchievementForm,
    BacklogForm,
    CurrentFocusForm,
    JarEntryForm,
    TaskForm,
)
from application.models import Achievement, BacklogItem, CurrentFocus, SlackingJarEntry, Task, User


main_bp = Blueprint("main", __name__)


@main_bp.app_context_processor
def inject_layout_context():
    return {"current_user": current_user}


def _user_choices():
    users = User.query.order_by(User.name.asc()).all()
    return [(u.id, u.name) for u in users]


@main_bp.route("/dashboard")
@login_required
def dashboard():
    tasks = Task.query.order_by(Task.updated_at.desc()).limit(6).all()
    all_tasks = Task.query.all()
    achievements = Achievement.query.order_by(Achievement.created_at.desc()).limit(4).all()
    fines = SlackingJarEntry.query.order_by(SlackingJarEntry.date_issued.desc()).all()

    unpaid_fines = [fine for fine in fines if not fine.is_paid]
    total_unpaid = sum(f.amount for f in unpaid_fines)
    total_collected = sum(f.amount for f in fines if f.is_paid)

    top_offender = None
    if fines:
        totals = {}
        for fine in fines:
            totals[fine.target_user.name] = totals.get(fine.target_user.name, 0) + fine.amount
        if totals:
            offender_name, offender_amount = sorted(
                totals.items(), key=lambda item: item[1], reverse=True
            )[0]
            top_offender = {"name": offender_name, "amount": offender_amount}

    task_counts = {
        "todo": len([t for t in all_tasks if t.status == "todo"]),
        "doing": len([t for t in all_tasks if t.status == "doing"]),
        "done": len([t for t in all_tasks if t.status == "done"]),
    }

    focus_by_user = {}
    for user in User.query.order_by(User.name.asc()).all():
        latest_focus = (
            CurrentFocus.query.filter_by(user_id=user.id)
            .order_by(CurrentFocus.updated_at.desc())
            .first()
        )
        focus_by_user[user.id] = latest_focus

    return render_template(
        "dashboard.html",
        active="dashboard",
        tasks=tasks,
        achievements=achievements,
        fines=fines,
        unpaid_fines=unpaid_fines,
        total_unpaid=total_unpaid,
        total_collected=total_collected,
        top_offender=top_offender,
        task_counts=task_counts,
        users=User.query.order_by(User.name.asc()).all(),
        focus_by_user=focus_by_user,
        focus_items=CurrentFocus.query.order_by(CurrentFocus.updated_at.desc()).all(),
    )


@main_bp.route("/board")
@login_required
def board():
    task_form = TaskForm()
    task_form.user_id.choices = _user_choices()
    owner_filter = request.args.get("owner", "mine")
    if owner_filter == "all":
        tasks = Task.query.order_by(Task.updated_at.desc()).all()
    else:
        tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.updated_at.desc()).all()
    grouped = {
        "todo": [t for t in tasks if t.status == "todo"],
        "doing": [t for t in tasks if t.status == "doing"],
        "done": [t for t in tasks if t.status == "done"],
    }
    return render_template(
        "board.html", active="board", grouped=grouped, form=task_form, owner_filter=owner_filter
    )


@main_bp.route("/tasks/create", methods=["POST"])
@login_required
def create_task():
    form = TaskForm()
    form.user_id.choices = _user_choices()
    if form.validate_on_submit():
        task = Task(
            title=form.title.data,
            description=form.description.data,
            status=form.status.data,
            priority=form.priority.data,
            deadline=form.deadline.data,
            user_id=form.user_id.data,
        )
        db.session.add(task)
        db.session.commit()
        flash("Task created.", "success")
    else:
        flash("Task validation failed.", "danger")
    return redirect(url_for("main.board"))


@main_bp.route("/tasks/<int:task_id>/update", methods=["POST"])
@login_required
def update_task(task_id: int):
    task = db.session.get(Task, task_id)
    if not task:
        abort(404)

    form = TaskForm()
    form.user_id.choices = _user_choices()
    if form.validate_on_submit():
        task.title = form.title.data
        task.description = form.description.data
        task.status = form.status.data
        task.priority = form.priority.data
        task.deadline = form.deadline.data
        task.user_id = form.user_id.data
        db.session.commit()
        flash("Task updated.", "success")
    else:
        flash("Task validation failed.", "danger")
    return redirect(url_for("main.board"))


@main_bp.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def update_task_status(task_id: int):
    task = db.session.get(Task, task_id)
    if not task:
        abort(404)

    target_status = request.form.get("status", "todo")
    if target_status not in {"todo", "doing", "done"}:
        flash("Invalid status.", "danger")
        return redirect(url_for("main.board"))

    task.status = target_status
    db.session.commit()
    flash("Task moved.", "success")
    return redirect(url_for("main.board"))


@main_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id: int):
    task = db.session.get(Task, task_id)
    if not task:
        abort(404)
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for("main.board"))


@main_bp.route("/tasks/<int:task_id>")
@login_required
def task_detail(task_id: int):
    task = db.session.get(Task, task_id)
    if not task:
        abort(404)
    return render_template("task_detail.html", active="board", task=task)


@main_bp.route("/tracker", methods=["GET", "POST"])
@login_required
def tracker():
    form = CurrentFocusForm()
    form.user_id.choices = _user_choices()

    if form.validate_on_submit():
        focus = CurrentFocus(
            user_id=form.user_id.data,
            title=form.title.data,
            description=form.description.data,
            status_note=form.status_note.data,
            target_date=form.target_date.data,
        )
        db.session.add(focus)
        db.session.commit()
        flash("Current focus saved.", "success")
        return redirect(url_for("main.tracker"))

    users = User.query.order_by(User.name.asc()).all()
    by_user = {u.id: [] for u in users}
    for item in CurrentFocus.query.order_by(CurrentFocus.updated_at.desc()).all():
        by_user[item.user_id].append(item)

    return render_template(
        "tracker.html", active="tracker", users=users, by_user=by_user, form=form
    )


@main_bp.route("/tracker/<int:focus_id>/delete", methods=["POST"])
@login_required
def delete_focus(focus_id: int):
    focus = db.session.get(CurrentFocus, focus_id)
    if not focus:
        abort(404)
    db.session.delete(focus)
    db.session.commit()
    flash("Focus item deleted.", "info")
    return redirect(url_for("main.tracker"))


@main_bp.route("/tracker/<int:focus_id>/update", methods=["POST"])
@login_required
def update_focus(focus_id: int):
    focus = db.session.get(CurrentFocus, focus_id)
    if not focus:
        abort(404)

    focus.title = request.form.get("title", focus.title)
    focus.description = request.form.get("description", focus.description)
    focus.status_note = request.form.get("status_note", focus.status_note)
    target_date_raw = request.form.get("target_date")
    if target_date_raw:
        focus.target_date = date.fromisoformat(target_date_raw)
    db.session.commit()
    flash("Focus item updated.", "success")
    return redirect(url_for("main.tracker"))


@main_bp.route("/backlog", methods=["GET", "POST"])
@login_required
def backlog():
    form = BacklogForm()
    if form.validate_on_submit():
        item = BacklogItem(
            title=form.title.data,
            description=form.description.data,
            category=form.category.data,
            created_by=current_user.id,
        )
        db.session.add(item)
        db.session.commit()
        flash("Backlog item added.", "success")
        return redirect(url_for("main.backlog"))

    category_filter = request.args.get("category", "all")
    query = BacklogItem.query.order_by(BacklogItem.created_at.desc())
    if category_filter in {"shared", "personal", "someday"}:
        query = query.filter_by(category=category_filter)

    return render_template(
        "backlog.html",
        active="backlog",
        form=form,
        category_filter=category_filter,
        items=query.all(),
    )


@main_bp.route("/backlog/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_backlog_item(item_id: int):
    item = db.session.get(BacklogItem, item_id)
    if not item:
        abort(404)
    db.session.delete(item)
    db.session.commit()
    flash("Backlog item removed.", "info")
    return redirect(url_for("main.backlog"))


@main_bp.route("/backlog/<int:item_id>/update", methods=["POST"])
@login_required
def update_backlog_item(item_id: int):
    item = db.session.get(BacklogItem, item_id)
    if not item:
        abort(404)

    item.title = request.form.get("title", item.title)
    item.description = request.form.get("description", item.description)
    category = request.form.get("category", item.category)
    if category in {"shared", "personal", "someday"}:
        item.category = category
    db.session.commit()
    flash("Backlog item updated.", "success")
    return redirect(url_for("main.backlog"))


@main_bp.route("/achievements", methods=["GET", "POST"])
@login_required
def achievements():
    form = AchievementForm()
    form.user_id.choices = _user_choices()
    if form.validate_on_submit():
        achievement = Achievement(
            title=form.title.data,
            description=form.description.data,
            user_id=form.user_id.data,
            date_achieved=form.date_achieved.data,
        )
        db.session.add(achievement)
        db.session.commit()
        flash("Achievement posted.", "success")
        return redirect(url_for("main.achievements"))

    people_filter = request.args.get("user", "all")
    query = Achievement.query.order_by(Achievement.date_achieved.desc(), Achievement.created_at.desc())
    if people_filter.isdigit():
        query = query.filter_by(user_id=int(people_filter))

    return render_template(
        "achievements.html",
        active="achievements",
        form=form,
        achievements=query.all(),
        users=User.query.order_by(User.name.asc()).all(),
        people_filter=people_filter,
    )


@main_bp.route("/achievements/<int:achievement_id>/delete", methods=["POST"])
@login_required
def delete_achievement(achievement_id: int):
    achievement = db.session.get(Achievement, achievement_id)
    if not achievement:
        abort(404)
    db.session.delete(achievement)
    db.session.commit()
    flash("Achievement deleted.", "info")
    return redirect(url_for("main.achievements"))


@main_bp.route("/achievements/<int:achievement_id>/update", methods=["POST"])
@login_required
def update_achievement(achievement_id: int):
    achievement = db.session.get(Achievement, achievement_id)
    if not achievement:
        abort(404)

    achievement.title = request.form.get("title", achievement.title)
    achievement.description = request.form.get("description", achievement.description)
    date_raw = request.form.get("date_achieved")
    if date_raw:
        achievement.date_achieved = date.fromisoformat(date_raw)
    db.session.commit()
    flash("Achievement updated.", "success")
    return redirect(url_for("main.achievements"))


@main_bp.route("/jar", methods=["GET", "POST"])
@login_required
def jar():
    form = JarEntryForm()
    form.user_id.choices = _user_choices()
    if request.method == "GET" and form.amount.data is None:
        form.amount.data = 1.0

    animate_drop = False
    if form.validate_on_submit():
        entry = SlackingJarEntry(
            user_id=form.user_id.data,
            issued_by=current_user.id,
            reason=form.reason.data,
            amount=form.amount.data,
            is_paid=False,
        )
        db.session.add(entry)
        db.session.commit()
        flash("Fine added.", "success")
        return redirect(url_for("main.jar", drop="1"))

    animate_drop = request.args.get("drop") == "1"
    entries = SlackingJarEntry.query.order_by(SlackingJarEntry.date_issued.desc()).all()
    total_fines = sum(e.amount for e in entries)
    fill_percent = min(20 + len(entries) * 8, 90)

    top_user = None
    user_totals = []
    if entries:
        user_totals = {}
        for entry in entries:
            user_totals[entry.target_user.name] = user_totals.get(entry.target_user.name, 0) + entry.amount
        name, amount = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)[0]
        top_user = {"name": name, "amount": amount}
        user_totals = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)

    return render_template(
        "jar.html",
        active="jar",
        form=form,
        entries=entries,
        total_fines=total_fines,
        fill_percent=fill_percent,
        top_user=top_user,
        user_totals=user_totals,
        animate_drop=animate_drop,
    )


@main_bp.route("/jar/<int:entry_id>")
@login_required
def fine_detail(entry_id: int):
    entry = db.session.get(SlackingJarEntry, entry_id)
    if not entry:
        abort(404)
    return render_template("fine_detail.html", active="jar", entry=entry)


@main_bp.route("/jar/<int:entry_id>/toggle-paid", methods=["POST"])
@login_required
def toggle_paid(entry_id: int):
    entry = db.session.get(SlackingJarEntry, entry_id)
    if not entry:
        abort(404)
    entry.is_paid = not entry.is_paid
    db.session.commit()
    flash("Fine status updated.", "success")
    return redirect(request.referrer or url_for("main.jar"))


@main_bp.route("/jar/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_fine(entry_id: int):
    entry = db.session.get(SlackingJarEntry, entry_id)
    if not entry:
        abort(404)
    db.session.delete(entry)
    db.session.commit()
    flash("Fine deleted.", "info")
    return redirect(url_for("main.jar"))


@main_bp.route("/jar/<int:entry_id>/update", methods=["POST"])
@login_required
def update_fine(entry_id: int):
    entry = db.session.get(SlackingJarEntry, entry_id)
    if not entry:
        abort(404)

    entry.reason = request.form.get("reason", entry.reason)
    amount = request.form.get("amount")
    if amount:
        try:
            entry.amount = max(1.0, float(amount))
        except ValueError:
            pass
    db.session.commit()
    flash("Fine updated.", "success")
    return redirect(url_for("main.fine_detail", entry_id=entry.id))
