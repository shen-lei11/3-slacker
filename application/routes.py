from datetime import date, timedelta

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


def _require_owner(record_owner_id, redirect_url, msg="You can only modify your own records."):
    """Check ownership; flash + redirect if unauthorized. Returns redirect response or None."""
    if current_user.id != record_owner_id:
        flash(msg, "danger")
        return redirect(redirect_url)
    return None


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

    total_fines = sum(f.amount for f in fines)
    total_entries = len(fines)
    fill_percent = min(20 + total_entries * 8, 90)

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
        total_fines=total_fines,
        total_entries=total_entries,
        top_offender=top_offender,
        fill_percent=fill_percent,
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
    search_query = request.args.get("q", "").strip()
    due_filter = request.args.get("due", "all")

    if owner_filter == "all":
        tasks = Task.query.order_by(Task.updated_at.desc()).all()
    else:
        tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.updated_at.desc()).all()

    if search_query:
        needle = search_query.lower()
        tasks = [
            task
            for task in tasks
            if needle in task.title.lower()
            or needle in (task.description.lower() if task.description else "")
        ]

    if due_filter == "soon":
        today = date.today()
        soon_cutoff = today + timedelta(days=3)
        tasks = [
            task
            for task in tasks
            if task.deadline and today <= task.deadline <= soon_cutoff
        ]

    grouped = {
        "todo": [t for t in tasks if t.status == "todo"],
        "doing": [t for t in tasks if t.status == "doing"],
        "done": [t for t in tasks if t.status == "done"],
    }
    return render_template(
        "board.html",
        active="board",
        grouped=grouped,
        form=task_form,
        owner_filter=owner_filter,
        search_query=search_query,
        due_filter=due_filter,
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
    denied = _require_owner(task.user_id, url_for("main.board"))
    if denied:
        return denied

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

    if request.args.get("next") == "detail":
        return redirect(url_for("main.task_detail", task_id=task.id))
    return redirect(url_for("main.board"))


@main_bp.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def update_task_status(task_id: int):
    task = db.session.get(Task, task_id)
    if not task:
        abort(404)
    denied = _require_owner(task.user_id, url_for("main.board"))
    if denied:
        return denied

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
    denied = _require_owner(task.user_id, url_for("main.board"))
    if denied:
        return denied
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
    denied = _require_owner(task.user_id, url_for("main.board"))
    if denied:
        return denied

    form = TaskForm(obj=task)
    form.user_id.choices = _user_choices()
    form.user_id.data = task.user_id

    return render_template("task_detail.html", active="board", task=task, form=form)


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
    denied = _require_owner(focus.user_id, url_for("main.tracker"))
    if denied:
        return denied
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
    denied = _require_owner(focus.user_id, url_for("main.tracker"))
    if denied:
        return denied

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
    search_query = request.args.get("q", "").strip()
    query = BacklogItem.query.order_by(BacklogItem.created_at.desc())
    if category_filter in {"shared", "personal", "someday"}:
        query = query.filter_by(category=category_filter)

    if search_query:
        like = f"%{search_query}%"
        query = query.filter(
            (BacklogItem.title.ilike(like)) | (BacklogItem.description.ilike(like))
        )

    items = query.all()
    activity_items = BacklogItem.query.order_by(BacklogItem.created_at.desc()).limit(5).all()

    return render_template(
        "backlog.html",
        active="backlog",
        form=form,
        category_filter=category_filter,
        search_query=search_query,
        items=items,
        activity_items=activity_items,
    )


@main_bp.route("/backlog/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_backlog_item(item_id: int):
    item = db.session.get(BacklogItem, item_id)
    if not item:
        abort(404)
    denied = _require_owner(item.created_by, url_for("main.backlog"))
    if denied:
        return denied
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
    denied = _require_owner(item.created_by, url_for("main.backlog"))
    if denied:
        return denied

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
    month_filter = request.args.get("month", "this")
    search_query = request.args.get("q", "").strip()

    query = Achievement.query.order_by(Achievement.date_achieved.desc(), Achievement.created_at.desc())
    if people_filter.isdigit():
        query = query.filter_by(user_id=int(people_filter))

    today = date.today()
    month_start = today.replace(day=1)
    if month_filter == "this":
        query = query.filter(Achievement.date_achieved >= month_start)

    if search_query:
        like = f"%{search_query}%"
        query = query.filter((Achievement.title.ilike(like)) | (Achievement.description.ilike(like)))

    achievements_list = query.all()

    wins_this_month = Achievement.query.filter(Achievement.date_achieved >= month_start).count()
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    wins_prev_month = Achievement.query.filter(
        Achievement.date_achieved >= prev_month_start,
        Achievement.date_achieved <= prev_month_end,
    ).count()
    if wins_prev_month > 0:
        wins_change_pct = int(((wins_this_month - wins_prev_month) / wins_prev_month) * 100)
    else:
        wins_change_pct = 100 if wins_this_month > 0 else 0

    all_achievements = Achievement.query.order_by(Achievement.date_achieved.desc()).all()
    streak_map = {}
    for achievement in all_achievements:
        streak_map[achievement.user.name] = streak_map.get(achievement.user.name, 0) + 1
    streak_rows = sorted(streak_map.items(), key=lambda row: row[1], reverse=True)

    current_longest_streak = streak_rows[0][1] if streak_rows else 0
    longest_streak_holder = streak_rows[0][0] if streak_rows else "N/A"

    jar_entries = SlackingJarEntry.query.all()
    jar_total_fines = sum(entry.amount for entry in jar_entries)

    return render_template(
        "achievements.html",
        active="achievements",
        form=form,
        achievements=achievements_list,
        users=User.query.order_by(User.name.asc()).all(),
        people_filter=people_filter,
        month_filter=month_filter,
        search_query=search_query,
        wins_this_month=wins_this_month,
        wins_change_pct=wins_change_pct,
        current_longest_streak=current_longest_streak,
        longest_streak_holder=longest_streak_holder,
        streak_rows=streak_rows[:3],
        jar_total_fines=jar_total_fines,
    )


@main_bp.route("/achievements/new", methods=["GET", "POST"])
@login_required
def new_achievement():
    form = AchievementForm()
    form.user_id.choices = _user_choices()

    if request.method == "GET" and not form.date_achieved.data:
        form.date_achieved.data = date.today()

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

    users = User.query.order_by(User.name.asc()).all()
    selected_user = users[0] if not form.user_id.data else next(
        (user for user in users if user.id == form.user_id.data),
        users[0] if users else None,
    )

    return render_template(
        "achievements_new.html",
        active="achievements",
        form=form,
        selected_user=selected_user,
    )


@main_bp.route("/achievements/<int:achievement_id>/delete", methods=["POST"])
@login_required
def delete_achievement(achievement_id: int):
    achievement = db.session.get(Achievement, achievement_id)
    if not achievement:
        abort(404)
    denied = _require_owner(achievement.user_id, url_for("main.achievements"))
    if denied:
        return denied
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
    denied = _require_owner(achievement.user_id, url_for("main.achievements"))
    if denied:
        return denied

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
    person_filter = request.args.get("person", "all")

    all_entries = SlackingJarEntry.query.order_by(SlackingJarEntry.date_issued.desc()).all()

    total_fines = sum(e.amount for e in all_entries)
    fill_percent = min(20 + len(all_entries) * 8, 90)

    top_user = None
    if all_entries:
        user_totals = {}
        for entry in all_entries:
            user_totals[entry.target_user.name] = user_totals.get(entry.target_user.name, 0) + entry.amount
        if user_totals:
            name, amount = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)[0]
            top_user = {"name": name, "amount": amount}

    entries = all_entries
    if person_filter.isdigit():
        entries = [entry for entry in entries if entry.user_id == int(person_filter)]

    return render_template(
        "jar.html",
        active="jar",
        form=form,
        entries=entries,
        users=User.query.order_by(User.name.asc()).all(),
        person_filter=person_filter,
        total_fines=total_fines,
        total_entries=len(all_entries),
        fill_percent=fill_percent,
        top_user=top_user,
        animate_drop=animate_drop,
    )


@main_bp.route("/jar/new", methods=["GET", "POST"])
@login_required
def new_fine():
    form = JarEntryForm()
    form.user_id.choices = _user_choices()

    if request.method == "GET" and form.amount.data is None:
        form.amount.data = 5.0

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
        flash("Fine issued.", "success")
        return redirect(url_for("main.jar"))

    recent_entries = SlackingJarEntry.query.order_by(SlackingJarEntry.date_issued.desc()).limit(5).all()
    total_fines = sum(entry.amount for entry in SlackingJarEntry.query.all())

    return render_template(
        "jar_new.html",
        active="jar",
        form=form,
        recent_entries=recent_entries,
        total_fines=total_fines,
        today=date.today(),
    )


@main_bp.route("/jar/<int:entry_id>")
@login_required
def fine_detail(entry_id: int):
    entry = db.session.get(SlackingJarEntry, entry_id)
    if not entry:
        abort(404)
    denied = _require_owner(entry.issued_by, url_for("main.jar"))
    if denied:
        return denied
    return render_template("fine_detail.html", active="jar", entry=entry)



@main_bp.route("/jar/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_fine(entry_id: int):
    entry = db.session.get(SlackingJarEntry, entry_id)
    if not entry:
        abort(404)
    denied = _require_owner(entry.issued_by, url_for("main.jar"))
    if denied:
        return denied
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
    denied = _require_owner(entry.issued_by, url_for("main.jar"))
    if denied:
        return denied

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
