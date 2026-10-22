"""The dashboard's whole state, one JSON file in the /data volume.

Small on purpose: a handful of rooms and a few dozen teams. Results are never stored here,
they are read live from the CTFd instances, which stay the source of truth.
"""

import json
import os
import threading

PATH = os.environ.get("STATE_FILE", "/data/state.json")
_lock = threading.Lock()

EMPTY = {
    "rooms": [],  # {id, name, url, token, subject, intro_id, door_id, challenge_ids, users: {login: user_id}}
    "teams": [],  # {login, password}
    "pauses": {},  # {room_id: {login: [[released_at, back_at or None], ...]}}: Release
    "started_at": None,
    "ended_at": None,
}


def load():
    with _lock:
        if not os.path.exists(PATH):
            return json.loads(json.dumps(EMPTY))
        with open(PATH) as f:
            return {**EMPTY, **json.load(f)}


def save(state):
    with _lock:
        tmp = PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, PATH)


def room(state, room_id):
    for r in state["rooms"]:
        if r["id"] == room_id:
            return r
    return None
