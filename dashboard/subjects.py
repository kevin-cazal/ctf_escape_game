"""How a room content gets into a room: the workshop platform's own importer.

`library.build_subject` writes the content out as a workshop-platform subject (welcome page,
`checkpoint` door step `porte`, one `flag` step per step), and `tools/sync_subject.py` of
ctfd-workshop-platform imports it, unchanged: the same code the plugin's admin sync page runs.
What that page does in the browser (supply the answers) is done by build_subject, and the
upload of each step's attachments (files/<step id>/, listed for the push in the generated
`attachments.yaml`) is done here.
"""

import contextlib
import io
import os
import sys
import tempfile

import yaml

TOOLS = os.environ.get("WORKSHOP_TOOLS", "/app/workshop-tools")
PLUGIN = os.environ.get("WORKSHOP_PLUGIN", "/app/workshop-plugin")
for _path in (TOOLS, PLUGIN):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import sync_subject  # noqa: E402  (ctfd-workshop-platform/tools)
from sync_subject import CTFdAdmin, slug_topic  # noqa: E402

DOOR = "porte"
INTRO = "__intro__"  # the welcome step the importer makes from intro.md; the door requires it


class SyncError(Exception):
    pass


def push(room, cid):
    """Import content `cid` into the room. Returns the importer's log and the ids of the
    welcome step, the door and the challenge steps."""
    import library
    out = io.StringIO()
    with tempfile.TemporaryDirectory() as tmp:
        work = os.path.join(tmp, cid)
        try:
            model = library.build_subject(cid, work)
        except library.ContentError as e:
            raise SyncError(str(e))
        url = room.get("api_url") or room["url"]
        ctfd = CTFdAdmin(url, token=room["token"])
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                sync_subject.sync(work, url, None, None, ctfd=ctfd)
        except SystemExit:
            raise SyncError("the importer refused the content:\n" + out.getvalue()[-1500:])
        except Exception as e:  # the importer raises RuntimeError on API errors
            raise SyncError(f"{e}\n{out.getvalue()[-1500:]}")

        # Downloadable files (same job as CTF_deployments/tools/upload_attachments.py)
        with open(os.path.join(work, "attachments.yaml")) as f:
            attachments = (yaml.safe_load(f) or {}).get("attachments") or []
        for att in attachments:
            if not ctfd.api("GET", f"/files?location={att['location']}"):
                ctfd.upload(os.path.join(work, att["path"]), att["location"])
                out.write(f"uploaded {att['location']}\n")

    ids = step_ids(ctfd, model)
    if ids["door_id"] is None or not ids["challenge_ids"] or None in ids["challenge_ids"]:
        raise SyncError(f"imported, but the door or a challenge step is missing: {ids}")
    return out.getvalue(), ids


def step_ids(ctfd, info):
    """Find the welcome step, the door and the challenge steps (in order) by the topic the
    importer gives each of them."""
    want = {slug_topic(info["slug"], INTRO): "intro", slug_topic(info["slug"], DOOR): "door"}
    for sid in [st["id"] for st in info["steps"]]:
        want[slug_topic(info["slug"], sid)] = sid
    found = {}
    for ch in ctfd.api("GET", "/challenges?view=admin") or []:
        for t in ctfd.api("GET", f"/challenges/{ch['id']}/topics") or []:
            if t["value"] in want:
                found[want[t["value"]]] = ch["id"]
    return {
        "intro_id": found.get("intro"),
        "door_id": found.get("door"),
        "challenge_ids": [found.get(st["id"]) for st in info["steps"]],
    }
