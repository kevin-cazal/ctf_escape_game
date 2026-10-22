"""Everything the dashboard does to a room, through the CTFd API only.

A room is one CTFd instance running the workshop plugin (image ctfd-custom), holding:
  - the team accounts (same logins and passwords in every room),
  - one subject, imported by the platform's own importer (see subjects.py):
    a welcome page, a `checkpoint` door step, then the challenge as a `flag` step.

"Let in" = the dashboard solves the team's door step (core POST /api/v1/submissions); staff
can also type the room code at the PC. Time spent in a room = solve date of the challenge
step - solve date of the door.
"""

import datetime
from concurrent.futures import ThreadPoolExecutor

import library
import subjects
from ctfd import CTFd, CTFdError

EMAIL_DOMAIN = "escape-game.example.org"

# Opens the room on the student's screen as soon as staff click "Let in", without a reload by
# hand. CTFd's own extension point (Admin > Config > Theme footer, injected on every page by
# base.html), so no plugin change: while the door step is on the page and not done, the page
# asks CTFd for its own solves every 3 s; once the door is among them, it says so and reloads.
# Student-facing, so French like the rest of the room. Between the markers only: anything an
# admin adds to the footer outside them is kept.
FOOTER_START = "<!-- escape-game:door -->"
FOOTER_END = "<!-- /escape-game:door -->"
FOOTER_SCRIPT = FOOTER_START + """<script>
(function () {
  var DOOR = "%(door)d";
  var step = document.querySelector('.ws-step[data-challenge-id="' + DOOR + '"]');
  if (!step || step.dataset.state === "done") return;
  async function tick() {
    if (step.dataset.state === "done") return;  // opened from this page, with the room code
    try {
      var r = await fetch("/api/v1/users/me/solves", {credentials: "same-origin"});
      var solves = r.ok ? (await r.json()).data : [];
      if (solves.some(function (s) { return String(s.challenge_id) === DOOR; })) {
        var note = document.createElement("div");
        note.textContent = "La salle est ouverte, c'est parti !";
        note.setAttribute("role", "status");
        note.style.cssText = "position:fixed;left:50%%;top:24px;transform:translateX(-50%%);z-index:2000;" +
          "background:#013afb;color:#fff;padding:14px 26px;border-radius:12px;font-size:20px;" +
          "font-weight:600;box-shadow:0 8px 24px rgb(0 0 0 / .25)";
        document.body.appendChild(note);
        setTimeout(function () { location.reload(); }, 1200);
        return;
      }
    } catch (e) { /* network hiccup: try again */ }
    setTimeout(tick, 3000);
  }
  setTimeout(tick, 3000);
})();
</script>""" + FOOTER_END


def api_url(room):
    """Where the dashboard reaches the room: inside the compose network when it knows the room's
    service (http://roomN:8000), else at its public URL. Students always get the public one."""
    return room.get("api_url") or room["url"]


def api(room):
    return CTFd(api_url(room), room["token"])


def parse_date(value):
    d = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)


# --- prepare -------------------------------------------------------------


def push_accounts(room, teams):
    """Create or update the team accounts. Idempotent."""
    c = api(room)
    c.check_admin()
    log = []
    logins = {t["login"] for t in teams}
    existing = {u["name"]: u for u in c.users()}
    users = {}
    for t in teams:
        u = existing.get(t["login"])
        if u is None:
            u = c.post("/users", {
                "name": t["login"],
                "email": f"{t['login']}@{EMAIL_DOMAIN}",
                "password": t["password"],
                "type": "user",
                "verified": True,
            })
            log.append(f"created {t['login']}")
        else:
            c.patch(f"/users/{u['id']}", {"password": t["password"]})
        users[t["login"]] = u["id"]
    for name, u in existing.items():
        if name.startswith("equipe") and name not in logins:
            c.delete(f"/users/{u['id']}")
            log.append(f"deleted {name}")
    room["users"] = users
    return log


def push(room, teams):
    """Accounts, then the room's subject through the platform's importer."""
    log = push_accounts(room, teams)
    importer_log, ids = subjects.push(room, room["subject"])
    room.pop("challenge_id", None)  # one-step rooms, before rooms could hold several
    room.update(ids)
    room["import_log"] = importer_log
    set_door_watch(room)
    return log


def set_door_watch(room):
    """Put FOOTER_SCRIPT, for this room's current door, into the theme footer."""
    c = api(room)
    try:
        current = c.get("/configs/theme_footer").get("value") or ""
    except CTFdError:  # never set on this instance yet
        current = ""
    if FOOTER_START in current and FOOTER_END in current:
        before, rest = current.split(FOOTER_START, 1)
        current = before + rest.split(FOOTER_END, 1)[1]
    c.patch("/configs", {"theme_footer": current.strip() + FOOTER_SCRIPT % {"door": room["door_id"]}})


def health(room, teams):
    """List of (ok, label) checks for one room."""
    checks = []
    c = api(room)
    try:
        c.check_admin()
    except CTFdError as e:
        return [(False, f"instance or token: {e}")]
    checks.append((True, "instance reachable, admin token valid"))
    if not room.get("subject"):
        return checks + [(False, "no content chosen")]
    challenges = {ch["id"]: ch for ch in c.challenges()}
    info = library.load(room["subject"])
    checks.append((room.get("door_id") in challenges, "door step present"))
    ids = room.get("challenge_ids") or []
    present = [cid for cid in ids if cid in challenges]
    checks.append((len(ids) == len(info["steps"]) and len(present) == len(ids),
                   f"{len(present)}/{len(info['steps'])} challenge step(s) present: {info['name']}"))
    unflagged = [challenges[cid]["name"] for cid in present
                 if len(c.get(f"/challenges/{cid}/flags")) != 1]
    checks.append((not unflagged, "flags set" if not unflagged else f"no flag: {', '.join(unflagged)}"))
    names = {u["name"] for u in c.users()}
    missing = [t["login"] for t in teams if t["login"] not in names]
    checks.append((not missing, "all team accounts exist" if not missing
                   else f"missing accounts: {', '.join(missing)}"))
    return checks


def reset(room):
    """Delete every submission (door openings included). Before the event only."""
    c = api(room)
    n = 0
    for kind in ("correct", "incorrect"):
        for s in c.get_all("/submissions", type=kind):
            c.delete(f"/submissions/{s['id']}")
            n += 1
    return n


# --- during the game -----------------------------------------------------


def authorize(room, login):
    """Solve the team's door. The door requires the welcome step ("J'ai lu"): a team that did
    not click it gets it solved too, else the room opens behind a door still drawn locked."""
    c = api(room)
    uid = room["users"][login]
    solved = {s["challenge_id"] for s in c.get_all("/submissions", type="correct", user_id=uid)}
    for cid in (room.get("intro_id"), room["door_id"]):
        if cid and cid not in solved:
            c.post("/submissions", {
                "challenge_id": cid,
                "user_id": uid,
                "type": "correct",
                "provided": "opened from the dashboard",
                "ip": "0.0.0.0",
            })


def cancel(room, login):
    """Undo an authorization, as long as the team has solved nothing in the room."""
    c = api(room)
    uid = room["users"][login]
    solves = c.get_all("/submissions", type="correct", user_id=uid)
    if any(s["challenge_id"] in room["challenge_ids"] for s in solves):
        raise CTFdError("this team already solved a step of the room: use Release instead")
    for s in solves:
        if s["challenge_id"] == room["door_id"]:
            c.delete(f"/submissions/{s['id']}")


def _room_events(room):
    c = api(room)
    return c.solves(), c.fails()


def _paused_seconds(pauses, until):
    """Seconds spent released (out of the room) before `until`."""
    total = 0
    for start, end in pauses:
        start = parse_date(start)
        end = parse_date(end) if end else until
        total += max(0, (min(end, until) - start).total_seconds())
    return total


def results(state):
    """Read every room and build the grid and the ranking.

    A room holds one or more challenge steps, in order. Its cell is:
      out      the team never entered
      waiting  it clicked « J'ai lu » there and waits to be let in
      in       let in, timer running, `solved`/`total` steps
      paused   let in, then released by staff: timer stopped, steps kept
      done     every step solved; `seconds` = last step - door, minus the paused time
    """
    rooms = [r for r in state["rooms"] if r.get("door_id") and r.get("challenge_ids")]
    ended = parse_date(state["ended_at"]) if state.get("ended_at") else None
    pauses_of = state.get("pauses") or {}
    grid = {t["login"]: {} for t in state["teams"]}
    errors = {}

    with ThreadPoolExecutor(max_workers=max(1, len(rooms))) as pool:
        fetched = {r["id"]: pool.submit(_room_events, r) for r in rooms}

    for r in rooms:
        try:
            solves, fails = fetched[r["id"]].result()
        except CTFdError as e:
            errors[r["id"]] = str(e)
            continue
        steps = set(r["challenge_ids"])
        login_of = {uid: login for login, uid in r.get("users", {}).items()}
        read, entered, solved, nfails = {}, {}, {}, {}
        for s in solves:
            login = login_of.get(s["user_id"])
            date = parse_date(s["date"])
            if login is None or (ended and date > ended):
                continue
            if s["challenge_id"] == r.get("intro_id"):
                read[login] = date
            elif s["challenge_id"] == r["door_id"]:
                entered[login] = date
            elif s["challenge_id"] in steps:
                solved.setdefault(login, []).append(date)
        for s in fails:
            login = login_of.get(s["user_id"])
            if login and s["challenge_id"] in steps:
                nfails[login] = nfails.get(login, 0) + 1
        for login in grid:
            done_dates = sorted(solved.get(login, []))
            cell = {"status": "out", "fails": nfails.get(login, 0),
                    "solved": len(done_dates), "total": len(steps)}
            pauses = (pauses_of.get(r["id"]) or {}).get(login) or []
            if login in entered:
                cell["entered_at"] = entered[login].isoformat()
                if len(done_dates) == len(steps):
                    end = done_dates[-1]
                    cell["status"] = "done"
                    cell["done_at"] = end.isoformat()
                    cell["seconds"] = max(0, int((end - entered[login]).total_seconds()
                                                 - _paused_seconds(pauses, end)))
                elif pauses and pauses[-1][1] is None:
                    stop = parse_date(pauses[-1][0])
                    cell["status"] = "paused"
                    cell["seconds"] = max(0, int((stop - entered[login]).total_seconds()
                                                 - _paused_seconds(pauses[:-1], stop)))
                else:
                    cell["status"] = "in"
                    # The browser ticks the timer from this instant: entry, shifted by the
                    # time spent released.
                    shift = _paused_seconds(pauses, ended or datetime.datetime.now(datetime.timezone.utc))
                    cell["clock_from"] = (entered[login] + datetime.timedelta(seconds=shift)).isoformat()
            elif login in read:
                cell["status"] = "waiting"
                cell["waiting_since"] = read[login].isoformat()
            grid[login][r["id"]] = cell

    # "Waiting" = the team clicked « J'ai lu » in a room that is not open for it yet: it sits at
    # that PC and wants in. A team waits in one room at most (the latest « J'ai lu »), and not
    # while it is inside another room; older ones are rooms it walked away from.
    for cells in grid.values():
        waiting = [rid for rid, c in cells.items() if c["status"] == "waiting"]
        busy = any(c["status"] == "in" for c in cells.values())
        latest = max(waiting, key=lambda rid: cells[rid]["waiting_since"], default=None)
        for rid in waiting:
            if busy or rid != latest:
                cells[rid]["status"] = "out"

    # Ranking: most rooms done, then most steps solved in the rooms not finished, then the
    # lowest total time of the rooms done.
    ranking = []
    for login, cells in grid.items():
        finished = [c for c in cells.values() if c["status"] == "done"]
        current = next((rid for rid, c in cells.items() if c["status"] == "in"), None)
        ranking.append({
            "login": login,
            "rooms_done": len(finished),
            "steps_partial": sum(c["solved"] for c in cells.values() if c["status"] != "done"),
            "total_seconds": sum(c["seconds"] for c in finished),
            "current": current,
        })
    key = lambda x: (-x["rooms_done"], -x["steps_partial"], x["total_seconds"])
    ranking.sort(key=lambda x: (*key(x), x["login"]))
    rank = 0
    for i, row in enumerate(ranking):
        if i == 0 or key(ranking[i - 1]) != key(row):
            rank = i + 1
        row["rank"] = rank

    return {"grid": grid, "ranking": ranking, "errors": errors}
