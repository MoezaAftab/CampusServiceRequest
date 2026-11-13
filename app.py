"""Flask web layer for the Campus Service Request System."""
import os
from functools import wraps

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

from models import CATEGORIES, PRIORITIES, Role, Status
from repository import Repository
from services import AuthService, NotFound, PermissionDenied, RequestService, ValidationError

DEMO_USERS = [
    ("student1", "student123", "Ayesha Khan", Role.STUDENT),
    ("student2", "student123", "Bilal Ahmed", Role.STUDENT),
    ("staff1", "staff123", "Usman Tariq", Role.STAFF),
    ("staff2", "staff123", "Sana Malik", Role.STAFF),
    ("admin", "admin123", "Admin Office", Role.ADMIN),
]


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.environ.get("DATABASE", "campus.db"),
        SEED_DEMO_USERS=True,
    )
    if config:
        app.config.update(config)

    repo = Repository(app.config["DATABASE"])
    repo.init_db()
    auth = AuthService(repo)
    svc = RequestService(repo)
    app.repo, app.auth_service, app.request_service = repo, auth, svc

    if app.config["SEED_DEMO_USERS"] and repo.count_users() == 0:
        for username, password, name, role in DEMO_USERS:
            auth.create_user(username, password, name, role)

    @app.before_request
    def load_user():
        uid = session.get("user_id")
        g.user = repo.get_user(uid) if uid else None

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = auth.authenticate(request.form.get("username"), request.form.get("password"))
            if user is None:
                flash("Invalid username or password.", "error")
                return render_template("login.html"), 401
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("index"))
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def index():
        status = request.args.get("status") or None
        items = svc.visible_requests(g.user, status)
        return render_template("requests.html", items=items, statuses=[s.value for s in Status], current=status)

    @app.route("/requests/new", methods=["GET", "POST"])
    @login_required
    def new_request():
        if g.user.role != Role.STUDENT:
            raise PermissionDenied("Only students can submit service requests.")
        form = {}
        if request.method == "POST":
            form = {k: request.form.get(k, "") for k in ("title", "category", "location", "description", "priority")}
            try:
                req = svc.submit(g.user, **form)
            except ValidationError as exc:
                for message in exc.errors:
                    flash(message, "error")
                return render_template("new_request.html", form=form, categories=CATEGORIES,
                                       priorities=PRIORITIES), 400
            flash(f"Request #{req.id} submitted.", "success")
            return redirect(url_for("index"))
        return render_template("new_request.html", form=form, categories=CATEGORIES, priorities=PRIORITIES)

    @app.route("/requests/<int:rid>")
    @login_required
    def detail(rid):
        req = svc.get_request(g.user, rid)
        staff = repo.list_users(Role.STAFF) if g.user.role == Role.ADMIN else []
        return render_template("detail.html", req=req, staff=staff, Status=Status)

    @app.route("/requests/<int:rid>/assign", methods=["POST"])
    @login_required
    def assign(rid):
        try:
            svc.assign(g.user, rid, int(request.form.get("staff_id", 0) or 0))
            flash("Request assigned.", "success")
        except ValidationError as exc:
            flash(exc.errors[0], "error")
        return redirect(url_for("detail", rid=rid))

    @app.route("/requests/<int:rid>/status", methods=["POST"])
    @login_required
    def change_status(rid):
        try:
            req = svc.update_status(g.user, rid, request.form.get("status", ""))
            flash(f"Status updated to {req.status.value}.", "success")
        except ValidationError as exc:
            flash(exc.errors[0], "error")
        return redirect(url_for("detail", rid=rid))

    @app.errorhandler(PermissionDenied)
    def forbidden(exc):
        return render_template("error.html", code=403, message=str(exc)), 403

    @app.errorhandler(NotFound)
    def not_found(exc):
        return render_template("error.html", code=404, message=str(exc)), 404

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
