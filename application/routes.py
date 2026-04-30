from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from application.forms import (
    AchievementForm,
    BacklogForm,
    CurrentFocusForm,
    JarEntryForm,
    TaskForm,
)
from application.supabase_client import sb


main_bp = Blueprint("main", __name__)


# ---------- helpers ----------

def _require_owner(record_owner_id, redirect_url, msg="You can only modify your own records."):
    if current_user.id != int(record_owner_id):
        flash(msg, "danger")
        return redirect(redirect_url)
    return None


def _users_sorted():
    return sb().table("users").select("id, name, email").order("name").execute().data or []


def _user_choices():
    return [(u["id"], u["name"]) for u in _users_sorted()]


def _get_or_404(table: str, record_id: int):
    res = sb().table(table).select("*").eq("id", record_id).limit(1).execute()
    if not res.data:
        abort(404)
    return res.data[0]


def _iso(d):
    return d.isoformat() if d else None


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    return value


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return value
    if isinstance(value, datetime):
        return value.date()
    return value


def _normalize_backlog_items(items, user_map):
    for item in items:
        item["created_at"] = _parse_dt(item.get("created_at"))
        if not item.get("creator"):
            creator = user_map.get(item.get("created_by"))
            item["creator"] = creator or {"name": "Unknown"}
    return items


def _normalize_tasks(tasks, user_map=None):
    for task in tasks:
        task["deadline"] = _parse_date(task.get("deadline"))
        task["updated_at"] = _parse_dt(task.get("updated_at"))
        task["created_at"] = _parse_dt(task.get("created_at"))
        if user_map and not task.get("user"):
            task["user"] = user_map.get(task.get("user_id"), {"name": "Unknown"})
    return tasks


def _normalize_focus(items):
    for item in items:
        item["target_date"] = _parse_date(item.get("target_date"))
        item["updated_at"] = _parse_dt(item.get("updated_at"))
    return items


def _normalize_achievements(items, user_map=None):
    for item in items:
        item["date_achieved"] = _parse_date(item.get("date_achieved"))
        item["created_at"] = _parse_dt(item.get("created_at"))
        if user_map and not item.get("user"):
            item["user"] = user_map.get(item.get("user_id"), {"name": "Unknown"})
    return items


def _normalize_fines(items, user_map=None):
    for item in items:
        item["date_issued"] = _parse_dt(item.get("date_issued"))
        if user_map:
            if not item.get("target_user"):
                item["target_user"] = user_map.get(item.get("user_id"), {"name": "Unknown"})
            if not item.get("issuer"):
                item["issuer"] = user_map.get(item.get("issued_by"), {"name": "Unknown"})
    return items


# ---------- layout ----------

@main_bp.app_context_processor
def inject_layout_context():
    return {"current_user": current_user}


# ---------- dashboard ----------

@main_bp.route("/dashboard")
@login_required
def dashboard():
    tasks = (
        sb()
        .table("tasks")
        .select("*, user:users!tasks_user_fk(id, name)")
        .order("updated_at", desc=True)
        .limit(6)
        .execute()
        .data
        or []
    )
    all_tasks = sb().table("tasks").select("status").execute().data or []
    achievements = (
        sb()
        .table("achievements")
        .select("*, user:users!achievements_user_fk(name)")
        .order("created_at", desc=True)
        .limit(4)
        .execute()
        .data
        or []
    )
    fines = (
        sb()
        .table("slacking_jar_entries")
        .select("*, target_user:users!sje_target_fk(name), issuer:users!sje_issuer_fk(name)")
        .order("date_issued", desc=True)
        .execute()
        .data
        or []
    )

    total_fines = sum(f["amount"] for f in fines)
    total_entries = len(fines)
    fill_percent = min(20 + total_entries * 8, 90)

    top_offender = None
    if fines:
        totals = {}
        for fine in fines:
            name = fine["target_user"]["name"]
            totals[name] = totals.get(name, 0) + fine["amount"]
        if totals:
            offender_name, offender_amount = sorted(totals.items(), key=lambda x: x[1], reverse=True)[0]
            top_offender = {"name": offender_name, "amount": offender_amount}

    task_counts = {
        "todo": sum(1 for t in all_tasks if t["status"] == "todo"),
        "doing": sum(1 for t in all_tasks if t["status"] == "doing"),
        "done": sum(1 for t in all_tasks if t["status"] == "done"),
    }

    users = _users_sorted()
    user_map = {u["id"]: u for u in users}
    tasks = _normalize_tasks(tasks, user_map)
    achievements = _normalize_achievements(achievements, user_map)
    fines = _normalize_fines(fines, user_map)
    all_focus = (
        sb().table("current_focus").select("*").order("updated_at", desc=True).execute().data or []
    )
    all_focus = _normalize_focus(all_focus)
    focus_by_user = {}
    for u in users:
        focus_by_user[u["id"]] = next((f for f in all_focus if f["user_id"] == u["id"]), None)

    today_label = datetime.now().strftime("%A, %b %d")
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
        users=users,
        focus_by_user=focus_by_user,
        focus_items=all_focus,
        today_label=today_label,
    )


# ---------- board / tasks ----------

@main_bp.route("/board")
@login_required
def board():
    task_form = TaskForm()
    task_form.user_id.choices = _user_choices()
    owner_filter = request.args.get("owner", "mine")
    search_query = request.args.get("q", "").strip()
    due_filter = request.args.get("due", "all")

    q = (
        sb()
        .table("tasks")
        .select("*, user:users!tasks_user_fk(id, name)")
        .order("updated_at", desc=True)
    )
    if owner_filter != "all":
        q = q.eq("user_id", current_user.id)
    tasks = q.execute().data or []

    if search_query:
        needle = search_query.lower()
        tasks = [
            t for t in tasks
            if needle in (t["title"] or "").lower()
            or needle in (t.get("description") or "").lower()
        ]

    if due_filter == "soon":
        today = date.today()
        soon_cutoff = today + timedelta(days=3)
        def _within(t):
            d = t.get("deadline")
            if not d:
                return False
            d = date.fromisoformat(d) if isinstance(d, str) else d
            return today <= d <= soon_cutoff
        tasks = [t for t in tasks if _within(t)]

    user_map = {u["id"]: u for u in _users_sorted()}
    tasks = _normalize_tasks(tasks, user_map)
    grouped = {
        "todo": [t for t in tasks if t["status"] == "todo"],
        "doing": [t for t in tasks if t["status"] == "doing"],
        "done": [t for t in tasks if t["status"] == "done"],
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
        sb().table("tasks").insert({
            "title": form.title.data,
            "description": form.description.data,
            "status": form.status.data,
            "priority": form.priority.data,
            "deadline": _iso(form.deadline.data),
            "user_id": form.user_id.data,
        }).execute()
        flash("Task created.", "success")
    else:
        flash("Task validation failed.", "danger")
    return redirect(url_for("main.board"))


@main_bp.route("/tasks/<int:task_id>/update", methods=["POST"])
@login_required
def update_task(task_id: int):
    res = (
        sb()
        .table("tasks")
        .select("*, user:users!tasks_user_fk(id, name)")
        .eq("id", task_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        abort(404)
    task = res.data[0]
    user_map = {u["id"]: u for u in _users_sorted()}
    task = _normalize_tasks([task], user_map)[0]
    denied = _require_owner(task["user_id"], url_for("main.board"))
    if denied:
        return denied

    form = TaskForm()
    form.user_id.choices = _user_choices()
    if form.validate_on_submit():
        sb().table("tasks").update({
            "title": form.title.data,
            "description": form.description.data,
            "status": form.status.data,
            "priority": form.priority.data,
            "deadline": _iso(form.deadline.data),
            "user_id": form.user_id.data,
        }).eq("id", task_id).execute()
        flash("Task updated.", "success")
    else:
        flash("Task validation failed.", "danger")

    if request.args.get("next") == "detail":
        return redirect(url_for("main.task_detail", task_id=task_id))
    return redirect(url_for("main.board"))


@main_bp.route("/tasks/<int:task_id>/status", methods=["POST"])
@login_required
def update_task_status(task_id: int):
    task = _get_or_404("tasks", task_id)
    denied = _require_owner(task["user_id"], url_for("main.board"))
    if denied:
        return denied

    target_status = request.form.get("status", "todo")
    if target_status not in {"todo", "doing", "done"}:
        flash("Invalid status.", "danger")
        return redirect(url_for("main.board"))

    sb().table("tasks").update({"status": target_status}).eq("id", task_id).execute()
    flash("Task moved.", "success")
    return redirect(url_for("main.board"))


@main_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id: int):
    task = _get_or_404("tasks", task_id)
    denied = _require_owner(task["user_id"], url_for("main.board"))
    if denied:
        return denied
    sb().table("tasks").delete().eq("id", task_id).execute()
    flash("Task deleted.", "info")
    return redirect(url_for("main.board"))


@main_bp.route("/tasks/<int:task_id>")
@login_required
def task_detail(task_id: int):
    task = _get_or_404("tasks", task_id)
    denied = _require_owner(task["user_id"], url_for("main.board"))
    if denied:
        return denied

    form = TaskForm(data={
        "title": task["title"],
        "description": task.get("description"),
        "status": task["status"],
        "priority": task["priority"],
        "deadline": date.fromisoformat(task["deadline"]) if task.get("deadline") else None,
        "user_id": task["user_id"],
    })
    form.user_id.choices = _user_choices()
    return render_template("task_detail.html", active="board", task=task, form=form)


# ---------- tracker / current focus ----------

@main_bp.route("/tracker", methods=["GET", "POST"])
@login_required
def tracker():
    form = CurrentFocusForm()
    form.user_id.choices = _user_choices()

    if form.validate_on_submit():
        sb().table("current_focus").insert({
            "user_id": form.user_id.data,
            "title": form.title.data,
            "description": form.description.data,
            "status_note": form.status_note.data,
            "target_date": _iso(form.target_date.data),
        }).execute()
        flash("Current focus saved.", "success")
        return redirect(url_for("main.tracker"))

    users = _users_sorted()
    by_user = {u["id"]: [] for u in users}
    items = (
        sb().table("current_focus").select("*").order("updated_at", desc=True).execute().data or []
    )
    items = _normalize_focus(items)
    for item in items:
        by_user.setdefault(item["user_id"], []).append(item)

    return render_template("tracker.html", active="tracker", users=users, by_user=by_user, form=form)


@main_bp.route("/tracker/<int:focus_id>/delete", methods=["POST"])
@login_required
def delete_focus(focus_id: int):
    focus = _get_or_404("current_focus", focus_id)
    denied = _require_owner(focus["user_id"], url_for("main.tracker"))
    if denied:
        return denied
    sb().table("current_focus").delete().eq("id", focus_id).execute()
    flash("Focus item deleted.", "info")
    return redirect(url_for("main.tracker"))


@main_bp.route("/tracker/<int:focus_id>/update", methods=["POST"])
@login_required
def update_focus(focus_id: int):
    focus = _get_or_404("current_focus", focus_id)
    denied = _require_owner(focus["user_id"], url_for("main.tracker"))
    if denied:
        return denied

    payload = {
        "title": request.form.get("title", focus["title"]),
        "description": request.form.get("description", focus.get("description")),
        "status_note": request.form.get("status_note", focus.get("status_note")),
    }
    target_date_raw = request.form.get("target_date")
    if target_date_raw:
        payload["target_date"] = target_date_raw
    sb().table("current_focus").update(payload).eq("id", focus_id).execute()
    flash("Focus item updated.", "success")
    return redirect(url_for("main.tracker"))


# ---------- backlog ----------

@main_bp.route("/backlog", methods=["GET", "POST"])
@login_required
def backlog():
    form = BacklogForm()
    if form.validate_on_submit():
        sb().table("backlog_items").insert({
            "title": form.title.data,
            "description": form.description.data,
            "category": form.category.data,
            "created_by": current_user.id,
        }).execute()
        flash("Backlog item added.", "success")
        return redirect(url_for("main.backlog"))

    category_filter = request.args.get("category", "all")
    search_query = request.args.get("q", "").strip()

    q = (
        sb()
        .table("backlog_items")
        .select("*, creator:users!backlog_items_creator_fk(id, name)")
        .order("created_at", desc=True)
    )
    if category_filter in {"shared", "personal", "someday"}:
        q = q.eq("category", category_filter)
    if search_query:
        like = f"%{search_query}%"
        q = q.or_(f"title.ilike.{like},description.ilike.{like}")
    items = q.execute().data or []

    activity_items = (
        sb()
        .table("backlog_items")
        .select("*, creator:users!backlog_items_creator_fk(id, name)")
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )

    user_map = {u["id"]: u for u in _users_sorted()}
    items = _normalize_backlog_items(items, user_map)
    activity_items = _normalize_backlog_items(activity_items, user_map)

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
    item = _get_or_404("backlog_items", item_id)
    denied = _require_owner(item["created_by"], url_for("main.backlog"))
    if denied:
        return denied
    sb().table("backlog_items").delete().eq("id", item_id).execute()
    flash("Backlog item removed.", "info")
    return redirect(url_for("main.backlog"))


@main_bp.route("/backlog/<int:item_id>/update", methods=["POST"])
@login_required
def update_backlog_item(item_id: int):
    item = _get_or_404("backlog_items", item_id)
    denied = _require_owner(item["created_by"], url_for("main.backlog"))
    if denied:
        return denied

    payload = {
        "title": request.form.get("title", item["title"]),
        "description": request.form.get("description", item.get("description")),
    }
    category = request.form.get("category", item["category"])
    if category in {"shared", "personal", "someday"}:
        payload["category"] = category
    sb().table("backlog_items").update(payload).eq("id", item_id).execute()
    flash("Backlog item updated.", "success")
    return redirect(url_for("main.backlog"))


# ---------- achievements ----------

@main_bp.route("/achievements", methods=["GET", "POST"])
@login_required
def achievements():
    form = AchievementForm()
    form.user_id.choices = _user_choices()
    if form.validate_on_submit():
        sb().table("achievements").insert({
            "title": form.title.data,
            "description": form.description.data,
            "user_id": form.user_id.data,
            "date_achieved": _iso(form.date_achieved.data),
        }).execute()
        flash("Achievement posted.", "success")
        return redirect(url_for("main.achievements"))

    people_filter = request.args.get("user", "all")
    month_filter = request.args.get("month", "this")
    search_query = request.args.get("q", "").strip()

    q = (
        sb()
        .table("achievements")
        .select("*, user:users!achievements_user_fk(name)")
        .order("date_achieved", desc=True)
        .order("created_at", desc=True)
    )
    if people_filter.isdigit():
        q = q.eq("user_id", int(people_filter))

    today = date.today()
    month_start = today.replace(day=1)
    if month_filter == "this":
        q = q.gte("date_achieved", month_start.isoformat())

    if search_query:
        like = f"%{search_query}%"
        q = q.or_(f"title.ilike.{like},description.ilike.{like}")

    achievements_list = q.execute().data or []
    user_map = {u["id"]: u for u in _users_sorted()}
    achievements_list = _normalize_achievements(achievements_list, user_map)

    wins_this_month = (
        sb()
        .table("achievements")
        .select("id", count="exact")
        .gte("date_achieved", month_start.isoformat())
        .execute()
        .count
        or 0
    )
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    wins_prev_month = (
        sb()
        .table("achievements")
        .select("id", count="exact")
        .gte("date_achieved", prev_month_start.isoformat())
        .lte("date_achieved", prev_month_end.isoformat())
        .execute()
        .count
        or 0
    )
    if wins_prev_month > 0:
        wins_change_pct = int(((wins_this_month - wins_prev_month) / wins_prev_month) * 100)
    else:
        wins_change_pct = 100 if wins_this_month > 0 else 0

    all_achievements = (
        sb()
        .table("achievements")
        .select("*, user:users!achievements_user_fk(name)")
        .order("date_achieved", desc=True)
        .execute()
        .data
        or []
    )
    all_achievements = _normalize_achievements(all_achievements, user_map)
    streak_map = {}
    for a in all_achievements:
        name = a["user"]["name"]
        streak_map[name] = streak_map.get(name, 0) + 1
    streak_rows = sorted(streak_map.items(), key=lambda r: r[1], reverse=True)
    current_longest_streak = streak_rows[0][1] if streak_rows else 0
    longest_streak_holder = streak_rows[0][0] if streak_rows else "N/A"

    jar_entries = sb().table("slacking_jar_entries").select("amount").execute().data or []
    jar_total_fines = sum(e["amount"] for e in jar_entries)

    return render_template(
        "achievements.html",
        active="achievements",
        form=form,
        achievements=achievements_list,
        users=_users_sorted(),
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
        sb().table("achievements").insert({
            "title": form.title.data,
            "description": form.description.data,
            "user_id": form.user_id.data,
            "date_achieved": _iso(form.date_achieved.data),
        }).execute()
        flash("Achievement posted.", "success")
        return redirect(url_for("main.achievements"))

    users = _users_sorted()
    selected_user = users[0] if not form.user_id.data else next(
        (u for u in users if u["id"] == form.user_id.data),
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
    a = _get_or_404("achievements", achievement_id)
    denied = _require_owner(a["user_id"], url_for("main.achievements"))
    if denied:
        return denied
    sb().table("achievements").delete().eq("id", achievement_id).execute()
    flash("Achievement deleted.", "info")
    return redirect(url_for("main.achievements"))


@main_bp.route("/achievements/<int:achievement_id>/update", methods=["POST"])
@login_required
def update_achievement(achievement_id: int):
    a = _get_or_404("achievements", achievement_id)
    denied = _require_owner(a["user_id"], url_for("main.achievements"))
    if denied:
        return denied

    payload = {
        "title": request.form.get("title", a["title"]),
        "description": request.form.get("description", a.get("description")),
    }
    date_raw = request.form.get("date_achieved")
    if date_raw:
        payload["date_achieved"] = date_raw
    sb().table("achievements").update(payload).eq("id", achievement_id).execute()
    flash("Achievement updated.", "success")
    return redirect(url_for("main.achievements"))


# ---------- slacking jar ----------

def _jar_select():
    return "*, target_user:users!sje_target_fk(name), issuer:users!sje_issuer_fk(name)"


@main_bp.route("/jar", methods=["GET", "POST"])
@login_required
def jar():
    form = JarEntryForm()
    form.user_id.choices = _user_choices()
    if request.method == "GET" and form.amount.data is None:
        form.amount.data = 1.0

    if form.validate_on_submit():
        sb().table("slacking_jar_entries").insert({
            "user_id": form.user_id.data,
            "issued_by": current_user.id,
            "reason": form.reason.data,
            "amount": form.amount.data,
            "is_paid": False,
        }).execute()
        flash("Fine added.", "success")
        return redirect(url_for("main.jar", drop="1"))

    animate_drop = request.args.get("drop") == "1"
    person_filter = request.args.get("person", "all")

    all_entries = (
        sb()
        .table("slacking_jar_entries")
        .select(_jar_select())
        .order("date_issued", desc=True)
        .execute()
        .data
        or []
    )
    user_map = {u["id"]: u for u in _users_sorted()}
    all_entries = _normalize_fines(all_entries, user_map)

    total_fines = sum(e["amount"] for e in all_entries)
    fill_percent = min(20 + len(all_entries) * 8, 90)

    top_user = None
    if all_entries:
        totals = {}
        for entry in all_entries:
            name = entry["target_user"]["name"]
            totals[name] = totals.get(name, 0) + entry["amount"]
        if totals:
            name, amount = sorted(totals.items(), key=lambda x: x[1], reverse=True)[0]
            top_user = {"name": name, "amount": amount}

    entries = all_entries
    if person_filter.isdigit():
        entries = [e for e in entries if e["user_id"] == int(person_filter)]

    return render_template(
        "jar.html",
        active="jar",
        form=form,
        entries=entries,
        users=_users_sorted(),
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
        sb().table("slacking_jar_entries").insert({
            "user_id": form.user_id.data,
            "issued_by": current_user.id,
            "reason": form.reason.data,
            "amount": form.amount.data,
            "is_paid": False,
        }).execute()
        flash("Fine issued.", "success")
        return redirect(url_for("main.jar"))

    recent_entries = (
        sb()
        .table("slacking_jar_entries")
        .select(_jar_select())
        .order("date_issued", desc=True)
        .limit(5)
        .execute()
        .data
        or []
    )
    user_map = {u["id"]: u for u in _users_sorted()}
    recent_entries = _normalize_fines(recent_entries, user_map)
    all_amounts = sb().table("slacking_jar_entries").select("amount").execute().data or []
    total_fines = sum(e["amount"] for e in all_amounts)

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
    res = (
        sb()
        .table("slacking_jar_entries")
        .select(_jar_select())
        .eq("id", entry_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        abort(404)
    entry = res.data[0]
    user_map = {u["id"]: u for u in _users_sorted()}
    entry = _normalize_fines([entry], user_map)[0]
    denied = _require_owner(entry["issued_by"], url_for("main.jar"))
    if denied:
        return denied
    return render_template("fine_detail.html", active="jar", entry=entry)


@main_bp.route("/jar/<int:entry_id>/delete", methods=["POST"])
@login_required
def delete_fine(entry_id: int):
    entry = _get_or_404("slacking_jar_entries", entry_id)
    denied = _require_owner(entry["issued_by"], url_for("main.jar"))
    if denied:
        return denied
    sb().table("slacking_jar_entries").delete().eq("id", entry_id).execute()
    flash("Fine deleted.", "info")
    return redirect(url_for("main.jar"))


@main_bp.route("/jar/<int:entry_id>/update", methods=["POST"])
@login_required
def update_fine(entry_id: int):
    entry = _get_or_404("slacking_jar_entries", entry_id)
    denied = _require_owner(entry["issued_by"], url_for("main.jar"))
    if denied:
        return denied

    payload = {"reason": request.form.get("reason", entry["reason"])}
    amount = request.form.get("amount")
    if amount:
        try:
            payload["amount"] = max(1.0, float(amount))
        except ValueError:
            pass
    sb().table("slacking_jar_entries").update(payload).eq("id", entry_id).execute()
    flash("Fine updated.", "success")
    return redirect(url_for("main.fine_detail", entry_id=entry_id))
