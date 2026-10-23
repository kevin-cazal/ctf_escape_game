"""Escape game dashboard: prepare the rooms, run the game, show the ranking.

One Flask app, one staff password. All CTFd calls happen here, on the server side: CTFd has
no CORS, and the admin tokens must never reach a browser.
"""

import datetime
import functools
import hmac
import os
import secrets
import shutil

from flask import (Flask, abort, flash, jsonify, redirect, render_template, request,
                   send_file, send_from_directory, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

import library
import subjects
import rooms
import store
from ctfd import CTFdError

app = Flask(__name__)
# Runs behind the client's HTTPS reverse proxy: trust its X-Forwarded-Proto / -Host.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.environ["SECRET_KEY"]
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "true") == "true",
                  PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=2))
PASSWORD = os.environ["DASHBOARD_PASSWORD"]

# The contents shipped in the image join the library on first start (never overwritten after).
library.seed_builtins()

# The default event, on the very first start (no state yet): 2 teams, and the rooms named in
# ROOM1_URL, ROOM2_URL... registered with ROOMS_ADMIN_TOKEN and given a built-in content each.
# After that the state is the staff's: nothing here runs again.
DEFAULT_TEAMS = 2
DEFAULT_CONTENTS = ["exemple_salle", "hex_dec"]  # the two demo rooms of subjects/


def first_start():
    if os.path.exists(store.PATH):
        return
    state = store.load()
    state["teams"] = [{"login": f"equipe{i:02d}", "password": None} for i in range(1, DEFAULT_TEAMS + 1)]
    for t in state["teams"]:
        t["password"] = new_password()
    token = os.environ.get("ROOMS_ADMIN_TOKEN", "")
    n = 1
    while os.environ.get(f"ROOM{n}_URL") and token:
        content = DEFAULT_CONTENTS[n - 1] if n <= len(DEFAULT_CONTENTS) else None
        state["rooms"].append({
            "id": f"room{n}", "name": f"Salle {n}", "url": os.environ[f"ROOM{n}_URL"].rstrip("/"),
            "api_url": f"http://room{n}:8000",  # the compose service: no detour through the proxy
            "token": token,
            "admin_login": "admin", "admin_password": os.environ.get("ROOMS_ADMIN_PASSWORD", ""), "subject": content if library.exists(content) else None,
            "door_id": None, "challenge_ids": [], "users": {}})
        n += 1
    store.save(state)

# Easy to read aloud and to type on a school keyboard: no accents, no look-alike characters.
WORDS = ["tigre", "pomme", "fusee", "nuage", "robot", "pirate", "cactus", "dragon", "lune",
         "volcan", "requin", "comete", "banane", "castor", "ninja", "orage", "radar", "sabre",
         "tortue", "zebre", "panda", "lama", "otarie", "phare", "boussole", "canyon"]


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def new_password():
    return f"{secrets.choice(WORDS)}{secrets.randbelow(90) + 10}"


def staff_only(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("staff"):
            if request.path.startswith("/api/"):
                abort(401)
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


@app.before_request
def csrf():
    """Same-origin check on every state-changing request."""
    if request.method == "POST":
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            abort(403)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if hmac.compare_digest(request.form.get("password", ""), PASSWORD):
            session.permanent = True
            session["staff"] = True
            return redirect(request.args.get("next") or url_for("live"))
        flash("Wrong password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@staff_only
def home():
    state = store.load()
    ready = state["rooms"] and state["teams"] and all(r.get("door_id") for r in state["rooms"])
    return redirect(url_for("live" if ready else "prepare"))


# --- prepare -------------------------------------------------------------


@app.route("/prepare")
@staff_only
def prepare():
    state = store.load()
    used = {}
    for r in state["rooms"]:
        if r.get("subject"):
            used.setdefault(r["subject"], []).append(r["name"])
    for r in state["rooms"]:
        # Rooms of this compose (reached at http://roomN:8000) share ROOMS_ADMIN_PASSWORD; a room
        # registered before the password was kept gets it here.
        if not r.get("admin_password") and r.get("api_url"):
            r["admin_login"] = r.get("admin_login") or "admin"
            r["admin_password"] = os.environ.get("ROOMS_ADMIN_PASSWORD", "")
    return render_template("prepare.html", state=state, catalog=library.all_contents(),
                           used=used, health=session.pop("health", None))


@app.route("/rooms", methods=["POST"])
@staff_only
def add_room():
    state = store.load()
    url = request.form["url"].strip().rstrip("/")
    token = request.form["token"].strip()
    if not url.startswith(("http://", "https://")):
        flash("The URL must start with https:// (or http://).", "error")
        return redirect(url_for("prepare"))
    if any(r["url"] == url for r in state["rooms"]):
        flash("This instance is already in the list.", "error")
        return redirect(url_for("prepare"))
    room = {"url": url, "token": token}
    internal = request.form.get("api_url", "").strip().rstrip("/")
    if internal:
        room["api_url"] = internal
    room["admin_login"] = request.form.get("admin_login", "").strip() or "admin"
    room["admin_password"] = request.form.get("admin_password", "")
    try:
        rooms.api(room).check_admin()
    except CTFdError as e:
        flash(f"Instance refused: {e}", "error")
        return redirect(url_for("prepare"))
    n = max([int(r["id"][4:]) for r in state["rooms"]] + [0]) + 1
    room.update(id=f"room{n}", name=request.form.get("name", "").strip() or f"Salle {n}",
                subject=None, door_id=None, challenge_ids=[], users={})
    state["rooms"].append(room)
    store.save(state)
    flash(f"{room['name']} added. Choose its challenge, then push.", "ok")
    return redirect(url_for("prepare"))


@app.route("/rooms/<room_id>", methods=["POST"])
@staff_only
def edit_room(room_id):
    state = store.load()
    room = store.room(state, room_id) or abort(404)
    if request.form.get("action") == "remove":
        state["rooms"].remove(room)
        flash(f"{room['name']} removed from the dashboard (the instance itself is untouched).", "ok")
    else:
        name = request.form.get("subject") or None
        if name and not library.exists(name):
            abort(400)
        room["subject"] = name
        room["name"] = request.form.get("name", room["name"]).strip() or room["name"]
        flash(f"{room['name']} updated. Push to apply it to the instance.", "ok")
    store.save(state)
    return redirect(url_for("prepare"))


@app.route("/teams", methods=["POST"])
@staff_only
def set_teams():
    state = store.load()
    count = max(1, min(99, int(request.form.get("count", 0) or 0)))
    keep = {t["login"]: t for t in state["teams"]}
    teams = []
    for i in range(1, count + 1):
        login = f"equipe{i:02d}"
        teams.append(keep.get(login) or {"login": login, "password": new_password()})
    state["teams"] = teams
    store.save(state)
    flash(f"{count} teams. Push to create their accounts in every room.", "ok")
    return redirect(url_for("prepare"))


@app.route("/push", methods=["POST"])
@staff_only
def push():
    state = store.load()
    if not state["teams"]:
        flash("Create the teams first.", "error")
        return redirect(url_for("prepare"))
    for room in state["rooms"]:
        if not room.get("subject"):
            flash(f"{room['name']}: no content chosen, skipped.", "error")
            continue
        try:
            log = rooms.push(room, state["teams"])
            accounts = f"Accounts: {', '.join(log)}." if log else "Accounts up to date."
            flash(f"{room['name']}: pushed. {accounts} Content imported.", "ok")
        except Exception as e:  # one room failing must not stop the others
            flash(f"{room['name']}: push failed. {e}", "error")
    store.save(state)
    return redirect(url_for("prepare"))


@app.route("/health", methods=["POST"])
@staff_only
def health():
    state = store.load()
    session["health"] = {r["id"]: rooms.health(r, state["teams"]) for r in state["rooms"]}
    return redirect(url_for("prepare") + "#health")


@app.route("/reset", methods=["POST"])
@staff_only
def reset():
    if request.form.get("confirm") != "RESET":
        flash("Type RESET to confirm.", "error")
        return redirect(url_for("prepare"))
    state = store.load()
    for room in state["rooms"]:
        try:
            n = rooms.reset(room)
            flash(f"{room['name']}: {n} submission(s) deleted.", "ok")
        except CTFdError as e:
            flash(f"{room['name']}: reset failed. {e}", "error")
    state["started_at"] = state["ended_at"] = None
    state["pauses"] = {}
    store.save(state)
    return redirect(url_for("prepare"))


@app.route("/cards")
@staff_only
def cards():
    return render_template("cards.html", state=store.load())


# --- room contents -------------------------------------------------------


def _used_by(state, cid):
    return [r["name"] for r in state["rooms"] if r.get("subject") == cid]


@app.route("/contents/new")
@staff_only
def new_content():
    model = {"id": "", "name": "", "source": {"kind": "created"},
             "steps": [{"id": "new0", "title": "", "description": "", "attachments": [],
                        "case_insensitive": True}]}
    return render_template("content.html", model=model, secrets={"flags": {}, "code": library.new_code()},
                           used=[], issues=[])


@app.route("/contents/<cid>")
@staff_only
def edit_content(cid):
    library.exists(cid) or abort(404)
    try:
        model, secrets_ = library.load(cid), library.load_secrets(cid)
    except library.ContentError:
        flash("This content's answers do not open with the current GPG_PASSPHRASE "
              "(it was changed after the content was saved).", "error")
        return redirect(url_for("prepare") + "#contents")
    return render_template("content.html", model=model, secrets=secrets_,
                           used=_used_by(store.load(), cid), issues=library.problems(model, secrets_))


@app.route("/contents", methods=["POST"])
@app.route("/contents/<cid>", methods=["POST"])
@staff_only
def save_content(cid=None):
    f = request.form
    if cid:
        library.exists(cid) or abort(404)
        model, secrets_ = library.load(cid), library.load_secrets(cid)
    else:
        name = f.get("name", "").strip() or "Nouvelle salle"
        cid = library.new_id(name)
        model = {"id": cid, "slug": "c-" + cid.replace("_", "-"), "source": {"kind": "created"}, "steps": []}
        secrets_ = {"flags": {}, "code": ""}
    before = {st["id"]: st for st in model.get("steps", [])}
    model["name"] = f.get("name", "").strip() or model.get("name") or "Nouvelle salle"
    secrets_["code"] = f.get("code", "").strip()
    steps, flags = [], {}
    for key in f.getlist("step"):  # in page order
        sid = key if key in before else library.new_step_id()
        old = before.get(key, {})
        files_dir = library.ROOT / cid / "files" / sid
        keep = set(f.getlist(f"keep-{key}"))
        for name in old.get("attachments", []):
            if name not in keep:
                (files_dir / name).unlink(missing_ok=True)
        attachments = [n for n in old.get("attachments", []) if n in keep]
        for up in request.files.getlist(f"files-{key}"):
            if not up or not up.filename:
                continue
            name = secure_filename(up.filename) or "fichier"
            files_dir.mkdir(parents=True, exist_ok=True)
            up.save(files_dir / name)
            if name not in attachments:
                attachments.append(name)
        steps.append({
            "id": sid,
            "title": f.get(f"title-{key}", "").strip(),
            "description": library.demote_headings(f.get(f"description-{key}", "").replace("\r\n", "\n").strip()),
            "points": old.get("points", 100),
            "case_insensitive": bool(f.get(f"case-{key}")),
            "attachments": attachments,
            "hints": old.get("hints", []),
        })
        flags[sid] = f.get(f"flag-{key}", "").strip()
    for gone in set(before) - {st["id"] for st in steps}:
        shutil.rmtree(library.ROOT / cid / "files" / gone, ignore_errors=True)
    model["steps"] = steps
    secrets_["flags"] = flags
    library.save(model, secrets_)
    issues = library.problems(model, secrets_)
    if issues:
        flash(f"{model['name']} saved, but not ready yet: " + "; ".join(issues), "error")
        return redirect(url_for("edit_content", cid=cid))
    used = _used_by(store.load(), cid)
    hint = f" Push to update {', '.join(used)}." if used else " Bind it to a room below."
    flash(f"{model['name']} saved.{hint}", "ok")
    return redirect(url_for("prepare") + "#contents")


@app.route("/contents/load", methods=["POST"])
@staff_only
def load_content():
    upload = request.files.get("zip")
    try:
        if upload and upload.filename:
            model = library.load_zip(upload.stream, upload.filename)
        else:
            model = library.load_source(request.form.get("repo", ""), request.form.get("ref", ""))
    except library.ContentError as e:
        flash(f"Cannot load: {e}", "error")
        return redirect(url_for("prepare") + "#contents")
    issues = library.problems(model, library.load_secrets(model["id"]))
    if issues:
        flash(f"{model['name']} loaded. To finish before it can go in a room: " + "; ".join(issues), "error")
    else:
        flash(f"{model['name']} loaded, with its flags.", "ok")
    return redirect(url_for("edit_content", cid=model["id"]))


@app.route("/contents/<cid>/delete", methods=["POST"])
@staff_only
def delete_content(cid):
    library.exists(cid) or abort(404)
    used = _used_by(store.load(), cid)
    if used:
        flash(f"Still in {', '.join(used)}: choose another content for it first.", "error")
    else:
        name = library.load(cid)["name"]
        library.delete(cid)
        flash(f"{name} deleted.", "ok")
    return redirect(url_for("prepare") + "#contents")


@app.route("/contents/example.zip")
@staff_only
def example_zip():
    """A minimal room content in the right format, with a README: something to start from."""
    import io
    import zipfile
    root = os.path.join(library.BUILTIN, "exemple_salle")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in os.walk(root):
            for name in sorted(files):
                path = os.path.join(folder, name)
                z.write(path, os.path.join("exemple_salle", os.path.relpath(path, root)))
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name="exemple_salle.zip")


@app.route("/contents/<cid>/export")
@staff_only
def export_content(cid):
    library.exists(cid) or abort(404)
    return send_file(library.export_zip(cid), mimetype="application/zip", as_attachment=True,
                     download_name=f"{cid}.zip")


@app.route("/contents/<cid>/files/<sid>/<name>")
@staff_only
def content_file(cid, sid, name):
    library.exists(cid) or abort(404)
    return send_from_directory(library.ROOT / cid / "files" / sid, name, as_attachment=True)


# --- during the game -----------------------------------------------------


@app.route("/live")
@staff_only
def live():
    return render_template("live.html", state=store.load())


@app.route("/ranking")
@staff_only
def ranking():
    return render_template("ranking.html", state=store.load(), screen=bool(request.args.get("screen")))


@app.route("/api/results")
@staff_only
def api_results():
    state = store.load()
    data = rooms.results(state)
    data.update(
        now=now().isoformat(),
        rooms=[{"id": r["id"], "name": r["name"],
                "url": r["url"],
                "challenge": library.load(r["subject"])["name"] if library.exists(r.get("subject")) else None,
                "steps": len(r.get("challenge_ids") or [])}
               for r in state["rooms"] if r.get("door_id") and r.get("challenge_ids")],
        started_at=state["started_at"],
        ended_at=state["ended_at"],
    )
    return jsonify(data)


@app.route("/api/authorize", methods=["POST"])
@staff_only
def api_authorize():
    body = request.get_json(force=True)
    state = store.load()
    if state.get("ended_at"):
        return jsonify(error="The game is over."), 409
    room = store.room(state, body.get("room")) or abort(404)
    login = body.get("login")
    if login not in room.get("users", {}):
        return jsonify(error="Unknown team in this room: push again."), 409
    grid = rooms.results(state)["grid"].get(login, {})
    if not body.get("force"):
        busy = [rid for rid, c in grid.items() if c["status"] == "in" and rid != room["id"]]
        if busy:
            name = store.room(state, busy[0])["name"]
            return jsonify(error=f"{login} is still in {name}.", busy=busy[0]), 409
    if grid.get(room["id"], {}).get("status") == "paused":
        # Back into a room it was released from: the door is already open in CTFd, only the
        # dashboard's clock restarts.
        state["pauses"][room["id"]][login][-1][1] = now().isoformat()
        store.save(state)
        return jsonify(ok=True)
    try:
        rooms.authorize(room, login)
    except CTFdError as e:
        return jsonify(error=str(e)), 502
    if not state.get("started_at"):
        state["started_at"] = now().isoformat()
        store.save(state)
    return jsonify(ok=True)


@app.route("/api/cancel", methods=["POST"])
@staff_only
def api_cancel():
    body = request.get_json(force=True)
    state = store.load()
    room = store.room(state, body.get("room")) or abort(404)
    try:
        rooms.cancel(room, body.get("login"))
    except (CTFdError, KeyError) as e:
        return jsonify(error=str(e)), 409
    (state.get("pauses") or {}).get(room["id"], {}).pop(body.get("login"), None)
    store.save(state)
    return jsonify(ok=True)


@app.route("/api/release", methods=["POST"])
@staff_only
def api_release():
    """The team leaves a room it has not finished: its solved steps stay, its clock for that
    room stops, and "Let in" later picks up where it stopped."""
    body = request.get_json(force=True)
    state = store.load()
    room = store.room(state, body.get("room")) or abort(404)
    login = body.get("login")
    cell = rooms.results(state)["grid"].get(login, {}).get(room["id"], {})
    if cell.get("status") != "in":
        return jsonify(error=f"{login} is not inside {room['name']}."), 409
    pauses = state.setdefault("pauses", {}).setdefault(room["id"], {}).setdefault(login, [])
    pauses.append([now().isoformat(), None])
    store.save(state)
    return jsonify(ok=True)


@app.route("/game", methods=["POST"])
@staff_only
def game():
    state = store.load()
    if request.form.get("action") == "end":
        state["ended_at"] = now().isoformat()
        flash("Game over: the ranking is final. Solves after this moment do not count.", "ok")
    else:
        state["ended_at"] = None
        flash("Game reopened.", "ok")
    store.save(state)
    return redirect(request.referrer or url_for("live"))


first_start()
