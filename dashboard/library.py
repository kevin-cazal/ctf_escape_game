"""The room contents the dashboard knows: built in, loaded from a public git repository, or
created in the dashboard. One editable model for all three.

A content is a directory of /data/contents:

    model.json          {id, name, slug, source, steps: [{id, title, description, points,
                         case_insensitive, attachments: [filename], hints: [markdown]}]}
    secrets.json.gpg    {"flags": {step id: flag}, "code": room code}, GPG_PASSPHRASE
    files/<step>/...    the step's attachments: every file of the folder (shown inline too when it
                        is an image, and always offered as a download)
    assets/<path>       images a description shows with ![...](<path>), <path> relative to the
                        subject's .md (kept as written; copied back to <path> at build time)

At push time `build_subject` writes it out as a workshop-platform subject (the convention of
ctfd-workshop-platform's docs/CONTENT_CONVENTION.md): a welcome page, a `checkpoint` door step
`porte`, then one `flag` step per step of the model. That subject is what the platform's own
importer receives (subjects.py).
"""

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

import yaml

import subjects  # noqa: F401  (puts the platform's tools on sys.path)
from ws_parser import find_asset_refs, load_checkpoint_codes, load_flags, parse_subject

ROOT = Path(os.environ.get("CONTENTS_DIR", "/data/contents"))
BUILTIN = Path(os.environ.get("SUBJECTS_DIR", "/app/subjects"))
DOOR = "porte"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
CODE_WORDS = ["tigre", "pomme", "fusee", "nuage", "robot", "pirate", "cactus", "dragon", "lune",
              "volcan", "requin", "comete", "banane", "castor", "ninja", "orage", "radar",
              "sabre", "tortue", "zebre", "panda", "lama", "otarie", "phare", "boussole"]

# Student-facing, French like the challenges. The same for every room.
WELCOME = """# {name}

Bienvenue dans cette salle de l'escape game !

1. Connecte-toi avec le login de ton équipe.
2. Clique sur « J'ai lu » : l'encadrant voit que ton équipe attend devant cette salle.
3. L'encadrant ouvre la salle : ton chrono démarre et l'énigme s'affiche toute seule.
4. Résous l'énigme et valide le flag.
5. Bravo ! Passe à la salle suivante.
"""
DOOR_STEP = """## Entrée dans la salle
<!-- ws: {type: exercise, id: porte, validation: checkpoint, points: 0} -->

Appelle un encadrant : il ouvre la salle pour ton équipe et ton chrono démarre.
"""
DOWNLOADS = "**Fichiers à télécharger :**"


class ContentError(Exception):
    """Something staff should read, not a traceback."""


# --- storage -------------------------------------------------------------


def _gpg(args, data):
    passphrase = os.environ.get("GPG_PASSPHRASE", "")
    if not passphrase:
        raise ContentError("GPG_PASSPHRASE is not set")
    os.makedirs("/tmp/gnupg", mode=0o700, exist_ok=True)
    with tempfile.NamedTemporaryFile() as pw:
        pw.write(passphrase.encode())
        pw.flush()
        r = subprocess.run(["gpg", "--batch", "--quiet", "--yes", "--pinentry-mode", "loopback",
                            "--passphrase-file", pw.name, *args],
                           input=data, capture_output=True,
                           env={**os.environ, "GNUPGHOME": "/tmp/gnupg"})
    if r.returncode:
        raise ContentError("GPG failed: wrong GPG_PASSPHRASE?")
    return r.stdout


def decrypt_file(path):
    return _gpg(["--decrypt", str(path)], b"")


def all_contents():
    out = []
    if ROOT.is_dir():
        for d in sorted(ROOT.iterdir()):
            if (d / "model.json").is_file():
                out.append(load(d.name))
    return out


def exists(cid):
    return bool(cid) and re.fullmatch(r"[a-z0-9_-]+", cid) and (ROOT / cid / "model.json").is_file()


def load(cid):
    model = json.loads((ROOT / cid / "model.json").read_text())
    try:
        model["ready"] = not problems(model, load_secrets(cid))
    except ContentError:
        # GPG_PASSPHRASE changed since this content was saved: its answers no longer open.
        model["ready"] = False
        model["locked"] = True
    return model


def load_secrets(cid):
    path = ROOT / cid / "secrets.json.gpg"
    if not path.is_file():
        return {"flags": {}, "code": ""}
    return json.loads(decrypt_file(path))


def save(model, secrets_):
    d = ROOT / model["id"]
    d.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in model.items() if k != "ready"}
    (d / "model.json").write_text(json.dumps(clean, indent=2, ensure_ascii=False))
    (d / "secrets.json.gpg").write_bytes(
        _gpg(["--symmetric", "--cipher-algo", "AES256", "--output", "-"],
             json.dumps(secrets_).encode()))


def delete(cid):
    shutil.rmtree(ROOT / cid)


def new_id(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")[:30] or "room"
    cid, n = base, 2
    while (ROOT / cid).exists():
        cid, n = f"{base}_{n}", n + 1
    return cid


def new_step_id():
    return "s" + secrets.token_hex(3)


def new_code():
    return f"{secrets.choice(CODE_WORDS)}{secrets.randbelow(90) + 10}"


def demote_headings(md):
    """Turn # and ## titles into ###, outside code blocks. The room page uses levels 1 and 2 for
    the room and its steps, so a level 1 or 2 title in a description would cut the step in two;
    staff should not have to know that."""
    out, fence = [], False
    for line in md.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            fence = not fence
        elif not fence:
            line = re.sub(r"^#{1,2}(?=\s)", "###", line)
        out.append(line)
    return "\n".join(out)


def problems(model, secrets_):
    """What stops this content from going into a room."""
    out = []
    if not model.get("steps"):
        out.append("no step")
    for i, s in enumerate(model.get("steps") or [], 1):
        if not s.get("title", "").strip():
            out.append(f"step {i} has no title")
        if not secrets_.get("flags", {}).get(s["id"], "").strip():
            out.append(f"step {i} ({s.get('title') or '?'}) has no flag")
    if not secrets_.get("code", "").strip():
        out.append("no room code")
    return out


# --- import a subject (built in, or from a git repository) ----------------


def from_subject(subject_dir, source, cid=None):
    """Turn a subject directory into a content. Its answers must already be in plaintext
    (flags.yaml, checkpoint_codes.yaml) in `subject_dir`; missing flags stay empty and the
    content is then not ready until they are typed in the editor."""
    subject_dir = Path(subject_dir)
    subject = parse_subject(subject_dir)
    entry = subject.manifest.get("project", {}).get("entrypoint")
    flags = load_flags(subject_dir)
    codes = load_checkpoint_codes(subject_dir)

    exercises = [ex for doc in subject.documents if doc.path != entry for ex in doc.exercises]
    titles = {doc.title for doc in subject.documents} | {ch.title for doc in subject.documents
                                                         for ch in doc.chapters}
    others = [f"{ex.title} ({ex.validation})" for ex in exercises
              if ex.slug != DOOR and ex.validation != "flag"]
    if others:
        raise ContentError("a room only holds flag steps; this subject also has: " + ", ".join(others))
    steps = [ex for ex in exercises if ex.slug != DOOR]
    if not steps:
        raise ContentError("this subject has no flag step")

    cid = cid or new_id(subject.name)
    dest = ROOT / cid
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    model = {"id": cid, "name": subject.name, "slug": subject.slug, "source": source, "steps": []}
    found_flags = {}
    for ex in steps:
        body = ex.body_md
        # Attachments (Option 1): every file in files/<step id>/, nothing to declare.
        files = []
        folder = subject_dir / "files" / ex.slug
        for f in sorted(folder.iterdir()) if folder.is_dir() else []:
            if f.is_file() and not f.name.startswith("."):
                target = dest / "files" / ex.slug / f.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(f, target)
                files.append(f.name)
        for ref in find_asset_refs(body):
            if ref.startswith(f"files/{ex.slug}/"):
                # an attachment is already shown inline by build_subject: drop the second link
                body = re.sub(r"!\[[^\]]*\]\(" + re.escape(ref) + r"\)\n?", "", body)
            elif (subject_dir / ref).is_file():
                # an image of the text: kept with the content, under the same path
                target = dest / "assets" / ref
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(subject_dir / ref, target)
        context = ex.context_md.strip()
        # The parser hands a chapter's own title to its first step as **Title**: not step text.
        lines = context.splitlines()
        if lines and lines[0].strip("* ").strip() in titles and lines[0].startswith("**"):
            context = "\n".join(lines[1:]).strip()
        description = demote_headings((context + "\n\n" if context else "") + body.strip())
        flag = flags.get(ex.slug)
        value = flag.get("value") if isinstance(flag, dict) else flag
        model["steps"].append({
            "id": ex.slug,
            "title": ex.title,
            "description": description,
            "points": ex.points,
            "case_insensitive": bool(flag.get("case_insensitive", True)) if isinstance(flag, dict) else True,
            "attachments": files,
            "hints": [h.content_md for h in ex.hints],
        })
        if value:
            found_flags[ex.slug] = str(value)
    save(model, {"flags": found_flags, "code": str(codes.get(DOOR) or new_code())})
    return load(cid)


def _decrypt_sidecars(directory):
    for f in Path(directory).glob("*.yaml.gpg"):
        try:
            Path(str(f)[:-4]).write_bytes(decrypt_file(f))
        except ContentError:
            pass  # another passphrase: those answers stay missing, to be typed in the editor


def seed_builtins():
    """Copy the contents shipped in the image into the library, once each: an edited one is
    never overwritten by a redeploy."""
    ROOT.mkdir(parents=True, exist_ok=True)
    for d in sorted(BUILTIN.iterdir()) if BUILTIN.is_dir() else []:
        if not (d / "subject.yaml").is_file() or (ROOT / d.name).exists():
            continue
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / d.name
            shutil.copytree(d, work)
            _decrypt_sidecars(work)
            from_subject(work, {"kind": "built-in"}, cid=d.name)


OWNER_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAX_UNZIPPED = 200 * 1024 * 1024


def _subject_root(directory, what):
    """The subject directory inside `directory`: its root, or its one top-level folder (the
    shape of a "Download ZIP" archive)."""
    directory = Path(directory)
    if (directory / "subject.yaml").is_file():
        return directory
    tops = [d for d in directory.iterdir() if not d.name.startswith(".")]
    if len(tops) == 1 and tops[0].is_dir() and (tops[0] / "subject.yaml").is_file():
        return tops[0]
    if (directory / "workshop.yaml").is_file():
        raise ContentError(f"{what} is a workshop of several subjects: load one of its subjects")
    raise ContentError(f"{what} has no subject.yaml at its root: not a workshop subject")


def load_source(source, ref):
    """Load a public workshop subject from `source`:

      owner/repo        GitHub, with the plugin's own fetcher (plugins/workshop/source.py)
      http(s)://...git  any git host (GitLab, Bitbucket, a self-hosted server): `git clone`
    """
    source, ref = source.strip(), ref.strip()
    if OWNER_REPO.match(source):
        return _from_github(source, ref)
    if re.match(r"^https?://", source):
        return _from_clone(source, ref)
    raise ContentError("give owner/repo (GitHub) or an http(s):// git URL")


def _from_github(repo, ref):
    from source import SourceError, materialize  # ctfd-workshop-platform/plugins/workshop/source.py
    with tempfile.TemporaryDirectory() as tmp:
        try:
            got = materialize(repo, ref or "main", tmp, log=lambda line: None)
        except SourceError as e:
            raise ContentError(str(e))
        except Exception as e:
            raise ContentError(f"cannot fetch {repo}: {e}")
        if got["kind"] != "subject":
            raise ContentError(f"{repo} is a workshop of several subjects: load one of its subjects")
        _decrypt_sidecars(got["dir"])
        return from_subject(got["dir"], {"kind": "github", "repo": repo, "ref": ref or "main",
                                         "sha": got["sha"][:7]})


def _from_clone(url, ref):
    # http(s) only, no prompt for credentials, no submodules: a public repository, read once.
    cmd = ["git", "-c", "protocol.allow=never", "-c", "protocol.http.allow=always",
           "-c", "protocol.https.allow=always", "clone", "--quiet", "--depth", "1",
           "--no-recurse-submodules"]
    if ref:
        cmd += ["--branch", ref]
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false"}
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "repo"
        try:
            r = subprocess.run([*cmd, "--", url, str(dest)], capture_output=True, text=True,
                               timeout=120, env=env)
        except subprocess.TimeoutExpired:
            raise ContentError(f"cloning {url} took more than 2 minutes")
        if r.returncode:
            raise ContentError(f"cannot clone {url}: {r.stderr.strip()[-300:] or 'git failed'}"
                               " (is it public?)")
        sha = subprocess.run(["git", "-C", str(dest), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        root = _subject_root(dest, url)
        _decrypt_sidecars(root)
        return from_subject(root, {"kind": "git", "repo": url, "ref": ref or "default branch",
                                   "sha": sha})


def load_zip(upload, filename):
    """Load a workshop subject from an uploaded .zip (a folder zipped, or GitHub's Download ZIP)."""
    import zipfile
    with tempfile.TemporaryDirectory() as tmp:
        try:
            archive = zipfile.ZipFile(upload)
        except zipfile.BadZipFile:
            raise ContentError(f"{filename} is not a zip file")
        total = 0
        dest = Path(tmp).resolve()
        for info in archive.infolist():
            total += info.file_size
            target = (dest / info.filename).resolve()
            if total > MAX_UNZIPPED or not str(target).startswith(str(dest) + os.sep) \
                    or (info.external_attr >> 16) & 0o170000 == 0o120000:  # no symlinks
                raise ContentError(f"{filename}: refused (too big, or a path that leaves the archive)")
        archive.extractall(dest)
        root = _subject_root(dest, filename)
        _decrypt_sidecars(root)
        return from_subject(root, {"kind": "zip", "file": filename})


# --- write a content out as a subject --------------------------------------


def _location(slug, path):
    """Same scheme as the platform (sync_subject.asset_location) and the converter, so the
    same file always lands on the same CTFd location."""
    digest = hashlib.sha1(path.read_bytes()).hexdigest()[:8]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip("-") or "file"
    return f"ws-{slug}/{stem}-{digest}{path.suffix.lower()}"


def build_subject(cid, dest, strict=True, export=False):
    """Write content `cid` as a subject directory `dest`, answers in plaintext. Raises
    ContentError if it is not ready, unless `strict` is off (export of a draft).

    For a push, each step also gets its attachments shown (images inline) and linked under
    DOWNLOADS, and `attachments.yaml` tells subjects.push what to upload where. For an export
    (`export`), neither: the subject keeps the authoring form, files in files/<step id>/."""
    model = load(cid)
    secrets_ = load_secrets(cid)
    bad = problems(model, secrets_)
    if bad and strict:
        raise ContentError("not ready: " + "; ".join(bad))
    src, dest = ROOT / cid, Path(dest)
    dest.mkdir(parents=True)
    if (src / "assets").is_dir():
        shutil.copytree(src / "assets", dest, dirs_exist_ok=True)
    slug = model["slug"]
    (dest / "subject.yaml").write_text(yaml.safe_dump({
        "schema_version": "2.0",
        "project": {"name": model["name"], "slug": slug, "summary": "", "entrypoint": "intro.md"},
        "platform": {"mode_default": "instructor_led", "validation_default": "flag",
                     "points_default": 100},
        "documents": ["intro.md", "room.md"],
    }, allow_unicode=True, sort_keys=False))
    (dest / "intro.md").write_text(WELCOME.format(name=model["name"]))

    parts = [f"# {model['name']}\n<!-- ws: {{type: chapter, topology: linear}} -->\n", DOOR_STEP]
    attachments, flags = [], {}
    for s in model["steps"]:
        text = [f"## {s['title'].strip()}",
                f"<!-- ws: {{type: exercise, id: {s['id']}, validation: flag, points: {int(s.get('points') or 100)}}} -->",
                "", s["description"].strip(), ""]
        links = []
        for name in s.get("attachments") or []:
            path = src / "files" / s["id"] / name
            rel = f"files/{s['id']}/{name}"
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(path, target)
            if export:
                continue
            loc = _location(slug, path)
            attachments.append({"path": rel, "location": loc})
            if path.suffix.lower() in IMAGE_EXT:
                text += [f"![{name}]({rel})", ""]
            links.append(f"- [{name}](/files/{loc})")
        if links:
            text += [DOWNLOADS, "", *links, ""]
        for h in s.get("hints") or []:
            text += ["<!-- ws: {type: hint, cost: 0} -->",
                     "<details><summary>Indice</summary>", "", h.strip(), "", "</details>", ""]
        parts.append("\n".join(text))
        if secrets_["flags"].get(s["id"]):
            flags[s["id"]] = {"value": secrets_["flags"][s["id"]],
                              "case_insensitive": bool(s.get("case_insensitive", True))}
    (dest / "room.md").write_text("\n".join(parts))
    if not export:
        (dest / "attachments.yaml").write_text(yaml.safe_dump({"attachments": attachments}))
    (dest / "flags.yaml").write_text(yaml.safe_dump({"flags": flags}, allow_unicode=True))
    if secrets_.get("code"):
        (dest / "checkpoint_codes.yaml").write_text(yaml.safe_dump({"codes": {DOOR: secrets_["code"]}}))
    return model


def export_zip(cid):
    """The content as a workshop subject in a zip: what "Load from a zip file" takes back, and
    what a subject repository holds. Answers only encrypted (*.yaml.gpg, GPG_PASSPHRASE), never
    in plaintext, as in the platform's public *_subject repositories."""
    import io
    import zipfile
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / cid
        build_subject(cid, root, strict=False, export=True)
        for name in ("flags.yaml", "checkpoint_codes.yaml"):
            plain = root / name
            if plain.is_file():
                (root / (name + ".gpg")).write_bytes(
                    _gpg(["--symmetric", "--cipher-algo", "AES256", "--output", "-"], plain.read_bytes()))
                plain.unlink()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(root.rglob("*")):
                if f.is_file():
                    z.write(f, f"{cid}/{f.relative_to(root)}")
    buf.seek(0)
    return buf
