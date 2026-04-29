from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from application.forms import LoginForm, RegisterForm
from application.models import User
from application.supabase_client import sb


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/", methods=["GET"])
def root_redirect():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        res = sb().table("users").select("*").eq("email", email).limit(1).execute()
        if res.data:
            user = User.from_row(res.data[0])
            if user.check_password(form.password.data):
                login_user(user)
                flash("Welcome back.", "success")
                next_url = request.args.get("next")
                return redirect(next_url or url_for("main.dashboard"))
        flash("Invalid email or password.", "danger")

    return render_template("login.html", form=form)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        existing = sb().table("users").select("id").eq("email", email).limit(1).execute()
        if existing.data:
            flash("That email is already in use. Please sign in.", "danger")
        else:
            inserted = (
                sb()
                .table("users")
                .insert(
                    {
                        "name": form.name.data.strip(),
                        "email": email,
                        "password_hash": User.hash_password(form.password.data),
                    }
                )
                .execute()
            )
            user = User.from_row(inserted.data[0])
            login_user(user)
            flash("Account created. Welcome to SquadSync.", "success")
            return redirect(url_for("main.dashboard"))

    return render_template("register.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
