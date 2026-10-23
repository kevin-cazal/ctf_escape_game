"""Video guide: preparing the infrastructure with docker compose (terminal left, browser right).

Needs a browser terminal on 127.0.0.1:7681 running the shell in tools/guide/bashrc (pyxtermjs:
`pyxtermjs --port 7681 --command bash --cmd-args="--rcfile tools/guide/bashrc"`, with
`window.term = term` added to its page), the passphrase in <work dir>/passphrase.txt, and
passwordless `sudo docker`. Records terminal and browser; put them side by side with the same
ffmpeg hstack as tools/record_demo.py, into demo/guide_infrastructure.mp4.
"""
import json, os, subprocess, sys, time
from playwright.sync_api import sync_playwright

CH = "/home/kc/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
W, H = 960, 1080
OUT = "demo/raw_guide"
T0 = time.time()
WORK = os.environ.get("GUIDE_WORK", "/tmp/egguide/work")  # where the shell of tools/guide/bashrc starts
def mark(w): print((round(time.time() - T0, 1), w), flush=True)

CAPTION_JS = open("tools/guide/caption.js").read()

def caption(page, text):
    for _ in range(10):
        try:
            page.evaluate("t => sessionStorage.setItem('demo-cap', t)", text); page.evaluate(CAPTION_JS); return
        except Exception:
            time.sleep(0.5)

BUFFER = """() => { const b = term.buffer.active; const out = [];
  for (let i = 0; i < b.length; i++) out.push(b.getLine(i).translateToString(true));
  return out.join('\\n'); }"""
LAST = """() => { const b = term.buffer.active; let i = b.baseY + b.cursorY;
  return b.getLine(i).translateToString(true); }"""

def type_cmd(t, cmd, delay=28):
    t.keyboard.type(cmd, delay=delay); time.sleep(0.4); t.keyboard.press("Enter")

def wait_prompt(t, timeout=900):
    end = time.time() + timeout
    time.sleep(0.6)
    while time.time() < end:
        if t.evaluate(LAST).startswith("serveur:") and t.evaluate(LAST).rstrip().endswith("$"):
            return
        time.sleep(0.4)
    raise TimeoutError("command did not finish")

def run(t, cmd, pause=1.5, timeout=900, delay=28):
    type_cmd(t, cmd, delay); wait_prompt(t, timeout); time.sleep(pause)

PLACEHOLDER = """<html><body style="margin:0;height:100vh;display:grid;place-items:center;background:#f6f7fb;
color:#555b71;font:600 30px system-ui,sans-serif;text-align:center"><div>Navigateur<br>
<span style="font-weight:400;font-size:22px">les pages s'ouvrent quand tout tourne</span></div></body></html>"""

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CH)
    tctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=OUT + "/terminal",
                         record_video_size={"width": W, "height": H})
    bctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=OUT + "/browser",
                         record_video_size={"width": W, "height": H}, locale="fr-FR")
    for c in (tctx, bctx):
        c.add_init_script(CAPTION_JS)
    t, w = tctx.new_page(), bctx.new_page()
    w.set_content(PLACEHOLDER)
    t.goto("http://127.0.0.1:7681/"); t.wait_for_function("() => window.term", timeout=60000)
    time.sleep(2); t.locator("#terminal").click(); time.sleep(0.5)
    t.keyboard.type("clear", delay=1); t.keyboard.press("Enter"); time.sleep(1)
    mark("start")

    # 1. Get the project
    caption(t, "1 · Récupérer le projet (avec son sous-module)")
    run(t, "git clone --recursive https://github.com/kevin-cazal/ctf_escape_game.git", 1, 300)
    run(t, "cd ctf_escape_game && ls", 3)

    # 2. Four rooms instead of two
    caption(t, "2 · Le compose lance 2 salles par défaut : on en ajoute 2")
    run(t, "grep -n '^  room' docker-compose.yml", 3)
    caption(t, "2 · Ouvrir docker-compose.yml : voici le bloc de la salle 2")
    type_cmd(t, "nano docker-compose.yml"); time.sleep(2)
    t.keyboard.press("F6"); time.sleep(0.6); t.keyboard.type("room2:", delay=60); t.keyboard.press("Enter"); time.sleep(4)
    caption(t, "2 · Le copier deux fois en room3 et room4, en changeant le 2 partout (port, base, Redis, nom, volume)")
    t.keyboard.press("F6"); time.sleep(0.6); t.keyboard.type("One MariaDB", delay=60); t.keyboard.press("Enter"); time.sleep(1)
    t.keyboard.press("Home"); time.sleep(0.5)
    t.evaluate("txt => term.paste(txt)", open("tools/guide/rooms34.yml").read()); time.sleep(1.5)
    t.keyboard.press("Control+Home") if False else None
    for _ in range(24): t.keyboard.press("ArrowUp")
    time.sleep(6)
    caption(t, "2 · Et déclarer leurs volumes, en bas du fichier")
    t.keyboard.press("F6"); time.sleep(0.6); t.keyboard.type("  room2-uploads:", delay=60); t.keyboard.press("Enter"); time.sleep(1)
    t.keyboard.press("End"); t.keyboard.press("Enter"); t.keyboard.type("  room3-uploads:", delay=50)
    t.keyboard.press("Enter"); t.keyboard.type("  room4-uploads:", delay=50); time.sleep(3)
    caption(t, "2 · Enregistrer (Ctrl+O) et quitter (Ctrl+X)")
    t.keyboard.press("F3"); time.sleep(0.8); t.keyboard.press("Enter"); time.sleep(1.2); t.keyboard.press("F2")
    wait_prompt(t); time.sleep(1)
    mark("compose edited")

    # 3. .env
    caption(t, "3 · Le fichier .env : ports, mots de passe et jeton admin, générés au hasard")
    env_lines = [
        "cat > .env <<EOF",
        "BIND_ADDRESS=127.0.0.1",
        "DASHBOARD_PORT=9180",
        "ROOM1_PORT=9181", "ROOM2_PORT=9182", "ROOM3_PORT=9183", "ROOM4_PORT=9184",
        "DASHBOARD_PASSWORD=demo-escape-game",
        "DASHBOARD_SECRET_KEY=$(openssl rand -hex 32)",
        "GPG_PASSPHRASE=$(openssl rand -hex 16)",
        "COOKIE_SECURE=false",
        "ROOMS_ADMIN_PASSWORD=$(openssl rand -hex 12)",
        "ROOMS_ADMIN_TOKEN=ctfd_$(openssl rand -hex 32)",
        "CTFD_SECRET_KEY=$(openssl rand -hex 32)",
        "DB_PASSWORD=$(openssl rand -hex 16)",
        "DB_ROOT_PASSWORD=$(openssl rand -hex 16)",
        "ROOM1_URL=http://localhost:9181", "ROOM2_URL=http://localhost:9182",
        "ROOM3_URL=http://localhost:9183", "ROOM4_URL=http://localhost:9184",
        "EOF",
    ]
    for line in env_lines:
        if line.startswith("GPG"):
            caption(t, "3 · Une phrase de passe à vous : elle chiffre les réponses que garde le tableau de bord")
        if line.startswith("COOKIE"):
            caption(t, "3 · En local, sans HTTPS : COOKIE_SECURE=false")
        if line.startswith("ROOMS_ADMIN_TOKEN"):
            caption(t, "3 · Le jeton admin : le même pour toutes les salles, préréglé dans chaque CTFd")
        if line.startswith("ROOM1_URL"):
            caption(t, "3 · L'adresse de chaque salle (ici localhost : le domaine et le proxy dépendent de votre infra)")
        type_cmd(t, line, 30)
        # wait for bash to echo the line and give the next "> " before typing on
        end = time.time() + 15
        while time.time() < end and not (t.evaluate(LAST).startswith("> ") or line == "EOF"):
            time.sleep(0.2)
        time.sleep(0.3)
    wait_prompt(t); time.sleep(1)
    # a dropped keystroke would leave a value empty: stop the take rather than film a broken .env
    bad = [l for l in open(os.path.join(WORK, "ctf_escape_game", ".env")).read().splitlines() if l.endswith("=")]
    if bad:
        raise SystemExit(f"broken .env, empty: {bad}")
    caption(t, "3 · Le jeton admin de chaque salle, à garder pour le tableau de bord")
    run(t, "grep ROOMS_ADMIN_TOKEN .env", 4)
    caption(t, "3 · Vérifier : le compose compte maintenant 4 salles")
    run(t, "docker compose config --services", 4)
    mark("env written")

    # 4. Start
    caption(t, "4 · Démarrer : tableau de bord, 4 salles CTFd, MariaDB et Redis")
    run(t, "docker compose up -d --build", 2, 1200, 40)
    caption(t, "4 · Attendre que les 4 salles répondent")
    run(t, "for p in 9181 9182 9183 9184; do until curl -sf -o /dev/null localhost:$p/login; do sleep 2; done; echo \"salle $p : OK\"; done", 1, 600, 15)
    run(t, "docker compose ps --format 'table {{.Service}}\\t{{.Status}}\\t{{.Ports}}'", 4, 60, 15)
    caption(t, "4 · Chaque salle accepte le jeton : il en est l'administrateur")
    run(t, "T=$(grep ROOMS_ADMIN_TOKEN .env | cut -d= -f2)", 0.5, 120, 20)
    run(t, "for p in 9181 9182 9183 9184; do echo -n \"$p : \"; curl -s -H \"Authorization: Token $T\" -H 'Content-Type: application/json' localhost:$p/api/v1/users/me | grep -o '\"name\": \"admin\"'; done", 4, 60, 12)
    mark("started")

    # 5. Browser: dashboard
    caption(t, "5 · Tout tourne : ouvrir le tableau de bord")
    w.goto("http://localhost:9180/login"); caption(w, "localhost:9180 · le tableau de bord du staff")
    time.sleep(2)
    w.locator("input[name=password]").click(); w.locator("input[name=password]").press_sequentially("demo-escape-game", delay=60)
    w.locator("button.primary").click(); w.wait_for_load_state("networkidle")
    w.goto("http://localhost:9180/prepare"); caption(w, "Les 4 salles sont déjà enregistrées, avec leur jeton et le login admin de chaque CTFd")
    time.sleep(6)
    mark("dashboard")

    # 6. Browser: each virgin room
    for n in (1, 2, 3, 4):
        w.goto(f"http://localhost:918{n}/login"); caption(w, f"localhost:918{n} · Salle {n} : une instance CTFd vierge, prête à recevoir son contenu")
        time.sleep(4)
    caption(t, "Prochaine étape : choisir les contenus des salles, puis Push (voir la démo)")
    caption(w, "Prochaine étape : contenus des salles, équipes, puis Push")
    w.goto("http://localhost:9180/prepare"); caption(w, "Prochaine étape : contenus des salles, équipes, puis Push")
    time.sleep(5)
    mark("end")
    paths = {"terminal": t.video.path(), "browser": w.video.path()}
    tctx.close(); bctx.close(); b.close()
    json.dump(paths, open(OUT + "/videos.json", "w"))
