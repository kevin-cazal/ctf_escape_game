"""Demo of a full escape-game session, filmed at once: staff dashboard (left), équipe 01 (top
right), équipe 02 (bottom right).

Continues the infrastructure guide: run it from the folder the guide cloned and configured (it
reads .env and subjects/ there), on that fresh local deployment (4 rooms on localhost, 2 teams,
nothing pushed yet), up to the final ranking. Records the three browsers.
Then put them side by side:

    python tools/record_demo.py
    ffmpeg -i <staff.webm> -i <equipe01.webm> -i <equipe02.webm> -filter_complex \\
      "[0:v]fps=25[s];[1:v]fps=25,scale=960:540[a];[2:v]fps=25,scale=960:540[b];[a][b]vstack[t];[s][t]hstack,drawbox=x=958:y=0:w=4:h=1080:color=0x0b0e1a:t=fill,drawbox=x=960:y=538:w=960:h=4:color=0x0b0e1a:t=fill,format=yuv420p,setsar=1[v]" \\
      -map "[v]" -c:v libx264 -crf 22 -movflags +faststart demo/escape_game_demo.mp4

The webm paths are in demo/raw/videos.json. Needs playwright and requests; reads .env.
"""
import json, os, sys, time, requests
from playwright.sync_api import sync_playwright

env = dict(l.strip().split("=", 1) for l in open(".env") if "=" in l)


def flags_of(subject):
    """The right answers, decrypted from the subject (never written in this file: the repo is public)."""
    import subprocess, yaml
    out = subprocess.run(["gpg", "--batch", "--quiet", "--pinentry-mode", "loopback", "--passphrase",
                          env["GPG_PASSPHRASE"], "-d", f"subjects/{subject}/flags.yaml.gpg"],
                         capture_output=True, check=True).stdout
    return {k: (v["value"] if isinstance(v, dict) else v) for k, v in yaml.safe_load(out)["flags"].items()}


FLAG = {**flags_of("hex_dec"), **flags_of("agent_064")}
# The deployment of the infrastructure guide (tools/record_guide_infra.py): one machine, localhost.
D = os.environ.get("DEMO_DASHBOARD", "http://localhost:9180")
R = {n: env.get(f"ROOM{n}_URL", f"http://localhost:918{n}") for n in (1, 2, 3, 4)}
TOKEN = env["ROOMS_ADMIN_TOKEN"]
CH = os.environ.get("CHROMIUM", "/home/kc/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
SW, SH = 960, 1080   # staff: left half
PW, PH = 1280, 720   # each team: a quarter, recorded larger then scaled to 960x540
OUT = os.environ.get("DEMO_OUT", "demo/raw")
log = []
T0 = time.time()
def mark(what): log.append((round(time.time() - T0, 1), what)); print(log[-1], flush=True)

CAPTION_JS = """
(() => {
  const show = () => {
    const t = sessionStorage.getItem('demo-cap'); if (!t || !document.body) return;
    let b = document.getElementById('demo-cap');
    if (!b) { b = document.createElement('div'); b.id = 'demo-cap'; document.body.appendChild(b); }
    b.textContent = t;
    b.style.cssText = 'position:fixed;left:16px;bottom:16px;z-index:99999;max-width:880px;' +
      'background:#0b0e1a;color:#fff;font:600 19px/1.35 system-ui,sans-serif;padding:12px 18px;' +
      'border-radius:10px;border-left:6px solid #00ff97;box-shadow:0 6px 20px rgb(0 0 0/.3)';
  };
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', show) : show();
})();
"""

def caption(page, text):
    for _ in range(10):  # a page may be reloading itself (the room opening): try again
        try:
            page.evaluate("t => sessionStorage.setItem('demo-cap', t)", text)
            page.evaluate(CAPTION_JS)
            return
        except Exception:
            time.sleep(0.5)

def flash(page, loc):
    loc.scroll_into_view_if_needed()
    loc.evaluate("e => { e.style.outline = '4px solid #ff5f3a'; e.style.outlineOffset = '3px'; }")
    time.sleep(0.6)

def click(page, loc, pause=0.8):
    # The live grid redraws itself every 3 s: an element can be replaced between the frame and
    # the click, so try again on a fresh one.
    for attempt in range(5):
        try:
            flash(page, loc); loc.click(timeout=5000, no_wait_after=True); break
        except Exception:
            if attempt == 4:
                raise
            time.sleep(0.4)
    time.sleep(pause)

def typ(loc, text, delay=55):
    loc.click(); loc.fill(""); loc.press_sequentially(text, delay=delay)

def admin(room):
    return {"Authorization": "Token " + TOKEN, "Content-Type": "application/json"}

def solve_as_admin(room, login, step_name):
    """The other team (not filmed) solving a step."""
    U = R[room] + "/api/v1"; h = admin(room)
    uid = [u for u in requests.get(U + "/users?view=admin", headers=h).json()["data"] if u["name"] == login][0]["id"]
    ch = [c for c in requests.get(U + "/challenges?view=admin", headers=h).json()["data"]
          if c["name"] == step_name and c["value"] > 0][-1]
    requests.post(U + "/submissions", headers=h, json={"challenge_id": ch["id"], "user_id": uid,
                  "type": "correct", "provided": "demo", "ip": "0.0.0.0"})

def answer(pg, step, text, pause=2.5):
    box = [d for d in pg.locator("details.ws-step").all()
           if d.locator(".ws-step-name").inner_text().strip() == step][-1]
    if not box.locator("input.ws-answer").is_visible():
        box.locator(".ws-step-summary").click(); time.sleep(0.6)
    box.scroll_into_view_if_needed()
    typ(box.locator("input.ws-answer"), text, delay=70)
    time.sleep(0.4)
    click(pg, box.locator("button.ws-submit-btn"), pause)

PLACEHOLDER = """<html><body style="margin:0;height:100vh;display:grid;place-items:center;background:#013afb;
background-image:linear-gradient(rgb(255 255 255/.045) 1px,transparent 1px),linear-gradient(90deg,rgb(255 255 255/.045) 1px,transparent 1px);
background-size:48px 48px;color:#fff;font:600 34px system-ui,sans-serif;text-align:center">
<div>{team}<br><span style="font-weight:400;font-size:24px;opacity:.85">arrive après la préparation…</span></div></body></html>"""


def enter(pg, room, login, teams, note):
    pg.goto(R[room] + "/login"); caption(pg, note)
    typ(pg.locator("input[name=name]"), login, 70)
    typ(pg.locator("input[name=password]"), teams[login], 70)
    click(pg, pg.locator("input[type=submit], button[type=submit]").first, 1)
    pg.wait_for_load_state("networkidle")
    click(pg, pg.locator("button.ws-submit-btn", has_text="J'ai lu"), 1.5)


DOOR_DONE = """() => [...document.querySelectorAll('details.ws-step')].some(d =>
    (d.querySelector('.ws-step-name') || {}).textContent.trim() === 'Entrée dans la salle'
    && d.dataset.state === 'done')"""


def opened(pg, note):
    """Wait until the room has opened on this screen (toast, then reload by itself)."""
    caption(pg, note)
    deadline = time.time() + 25
    while time.time() < deadline:
        try:
            if pg.evaluate(DOOR_DONE):
                break
        except Exception:
            pass  # reloading
        time.sleep(0.5)
    else:
        raise TimeoutError("the room did not open on " + pg.url)
    pg.wait_for_load_state("networkidle"); caption(pg, note); time.sleep(1.5)


def let_in_waiting(st, login, note):
    """Staff clicks Let in for `login` in the bar of waiting teams."""
    caption(st, note)
    team = "Équipe " + login[-2:]
    chip = st.locator("#waiting .wteam", has_text=team)
    chip.wait_for(timeout=15000); time.sleep(1.5)
    click(st, chip.locator(".letin"), 1.5)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CH)
    staff_ctx = b.new_context(viewport={"width": SW, "height": SH}, record_video_dir=OUT + "/staff",
                              record_video_size={"width": SW, "height": SH}, locale="fr-FR")
    ctx1 = b.new_context(viewport={"width": PW, "height": PH}, record_video_dir=OUT + "/equipe01",
                         record_video_size={"width": PW, "height": PH}, locale="fr-FR")
    ctx2 = b.new_context(viewport={"width": PW, "height": PH}, record_video_dir=OUT + "/equipe02",
                         record_video_size={"width": PW, "height": PH}, locale="fr-FR")
    for c in (staff_ctx, ctx1, ctx2):
        c.add_init_script(CAPTION_JS)
    st, p1, p2 = staff_ctx.new_page(), ctx1.new_page(), ctx2.new_page()
    st.on("dialog", lambda d: d.accept())
    p1.set_content(PLACEHOLDER.format(team="Équipe 01"))
    p2.set_content(PLACEHOLDER.format(team="Équipe 02"))
    mark("start")

    # ---------- 1. Staff: log in; the install already registered rooms and teams ----------
    st.goto(D + "/login"); caption(st, "Staff · connexion au tableau de bord")
    time.sleep(1.5)
    typ(st.locator("input[name=password]"), env["DASHBOARD_PASSWORD"], 60)
    click(st, st.locator("button.primary"), 1.5)
    st.goto(D + "/prepare")
    caption(st, "1 · Préparer : à l'installation, les salles sont déjà enregistrées (voir le guide)")
    time.sleep(4)

    # ---------- 2. Contents: the library, one content, then each room's choice ----------
    caption(st, "2 · Contenus des salles : la bibliothèque (créer, charger depuis git ou un zip)")
    st.locator("#contents").scroll_into_view_if_needed(); time.sleep(3.5)
    click(st, st.locator("#contents a", has_text="Hexadécimal et décimal").first, 2)
    caption(st, "2 · Un contenu : des étapes, chacune avec son texte, ses fichiers et son flag")
    time.sleep(2.5)
    st.mouse.wheel(0, 700); time.sleep(2); st.mouse.wheel(0, 900); time.sleep(2)
    st.goto(D + "/prepare")
    caption(st, "1 · Préparer : les salles 1 et 2 ont un contenu par défaut ; la salle 3 reçoit Faux texte")
    for n in (1, 2):
        flash(st, st.locator(f"select[form=f-room{n}]")); time.sleep(0.8)
    sel = st.locator("select[form=f-room3]"); flash(st, sel); sel.select_option("faux_texte"); time.sleep(0.8)
    click(st, st.locator("#f-room3 button[value=save]"), 1.5)
    caption(st, "2 · Charger un contenu depuis un zip : l'exemple fourni (2 étapes, un fichier, une image)")
    st.locator("#contents").scroll_into_view_if_needed(); time.sleep(1)
    with st.expect_download() as dl:
        click(st, st.locator("a", has_text="Download an example zip"), 1)
    zip_path = dl.value.path()
    st.locator("input[name=zip]").scroll_into_view_if_needed()
    flash(st, st.locator("input[name=zip]")); st.locator("input[name=zip]").set_input_files(zip_path); time.sleep(1)
    with st.expect_navigation():
        click(st, st.locator("form:has(input[name=zip]) button"), 0)
    caption(st, "2 · Chargé : on le relit dans l'éditeur")
    time.sleep(3); st.mouse.wheel(0, 600); time.sleep(2.5)
    st.goto(D + "/prepare"); caption(st, "1 · Préparer : la salle 4 reçoit le contenu chargé")
    sel = st.locator("select[form=f-room4]"); flash(st, sel); sel.select_option("exemple_de_salle"); time.sleep(0.8)
    click(st, st.locator("#f-room4 button[value=save]"), 1.5)
    mark("contents chosen")

    # ---------- 3. Teams ----------
    caption(st, "3 · Équipes : un login et un mot de passe par équipe, le même dans toutes les salles")
    st.locator("input[name=count]").scroll_into_view_if_needed()
    flash(st, st.locator(".teams")); time.sleep(3)
    teams = {}
    for chip in st.locator(".teams .team").all():
        login, pw = chip.inner_text().split()
        teams[login] = pw
    mark(f"teams {sorted(teams)}")

    # ---------- 5. Push and check ----------
    caption(st, "4 · Pousser : comptes, porte et énigmes sont importés dans chaque salle")
    with st.expect_navigation(timeout=600000):
        click(st, st.locator("button", has_text="Push to all rooms"), 0)
    time.sleep(3)
    caption(st, "4 · Vérifier : tout est prêt")
    with st.expect_navigation(timeout=120000):
        click(st, st.locator("button", has_text="Check all rooms"), 0)
    st.locator("#health").scroll_into_view_if_needed(); time.sleep(4)
    mark("pushed and checked")

    # ---------- 6. The two teams arrive ----------
    st.goto(D + "/live"); caption(st, "Pendant le jeu · la grille en direct")
    time.sleep(2)
    enter(p1, 2, "equipe01", teams, "Équipe 01 · devant la salle 2 : connexion, puis « J'ai lu »")
    enter(p2, 1, "equipe02", teams, "Équipe 02 · devant la salle 1 : connexion, puis « J'ai lu »")
    caption(p1, "Équipe 01 · attend que l'encadrant ouvre la salle")
    caption(p2, "Équipe 02 · attend que l'encadrant ouvre la salle")
    caption(st, "Pendant le jeu · deux équipes attendent, chacune devant sa salle")
    st.wait_for_selector("#waiting .wteam >> nth=1", timeout=15000); time.sleep(3)
    mark("both waiting")
    let_in_waiting(st, "equipe01", "Pendant le jeu · « Let in » : la salle s'ouvre, le chrono démarre")
    let_in_waiting(st, "equipe02", "Pendant le jeu · « Let in » pour l'équipe 02")
    opened(p1, "Équipe 01 · la salle s'ouvre toute seule")
    opened(p2, "Équipe 02 · la salle s'ouvre toute seule")
    mark("both rooms open")

    # ---------- 7. Both play ----------
    caption(st, "Pendant le jeu · chaque cellule : chrono, étapes, erreurs")
    caption(p1, "Équipe 01 · étape 1 : un mot en hexadécimal")
    answer(p1, "Hexadécimal", FLAG["hex"], 1)
    caption(p2, "Équipe 02 · décoder le message en base64 (une erreur d'abord)")
    answer(p2, "Agent 064", "ctf{Project}", 1.5)
    caption(p1, "Équipe 01 · étape 2 : un mot en décimal")
    answer(p1, "Décimal", FLAG["dec"], 1)
    answer(p2, "Agent 064", FLAG["agent_064"], 3)
    caption(p2, "Équipe 02 · salle 1 réussie")
    caption(st, "Pendant le jeu · l'équipe 02 a réussi la salle 1 : son temps est figé")
    mark("team 2 done room 1"); time.sleep(2)

    # ---------- 8. Équipe 02 moves to Salle 2, Équipe 01 finishes it ----------
    enter(p2, 2, "equipe02", teams, "Équipe 02 · passe à la salle 2")
    caption(p1, "Équipe 01 · étape 3 : le mélange (une erreur d'abord)")
    answer(p1, "Le mélange", "ctf{bravo agent}", 1.5)
    let_in_waiting(st, "equipe02", "Pendant le jeu · l'équipe 02 attend devant la salle 2 : « Let in »")
    answer(p1, "Le mélange", FLAG["mixed"], 2)
    caption(p1, "Équipe 01 · salle 2 réussie")
    opened(p2, "Équipe 02 · la salle 2 s'ouvre")
    mark("team 1 done room 2")

    # ---------- 9. Équipe 01 moves to Salle 1; Équipe 02 works on Salle 2 ----------
    enter(p1, 1, "equipe01", teams, "Équipe 01 · passe à la salle 1")
    caption(p2, "Équipe 02 · étape 1 : hexadécimal")
    answer(p2, "Hexadécimal", FLAG["hex"], 1)
    let_in_waiting(st, "equipe01", "Pendant le jeu · l'équipe 01 attend devant la salle 1 : « Let in »")
    opened(p1, "Équipe 01 · la salle 1 s'ouvre")
    caption(p2, "Équipe 02 · étape 2 : décimal")
    answer(p2, "Décimal", FLAG["dec"], 1)
    caption(p1, "Équipe 01 · décoder le message en base64")
    answer(p1, "Agent 064", FLAG["agent_064"], 2)
    caption(p1, "Équipe 01 · deux salles sur deux")
    caption(p2, "Équipe 02 · cherche encore l'étape 3…")
    caption(st, "Pendant le jeu · l'équipe 01 a fini, l'équipe 02 en est à 2/3 en salle 2")
    mark("team 1 done room 1"); time.sleep(4)

    # ---------- 10. End and final ranking ----------
    caption(st, "Fin · « End the game » : le classement est figé")
    click(st, st.locator("button", has_text="End the game"), 2.5)
    st.goto(D + "/ranking"); caption(st, "Fin · le classement, côté staff")
    time.sleep(2)
    for pg, ctx in ((p1, ctx1), (p2, ctx2)):
        for c in st.context.cookies():
            ctx.add_cookies([{k: c[k] for k in ("name", "value", "domain", "path", "secure", "httpOnly", "sameSite")}])
        pg.goto(D + "/ranking?screen=1"); caption(pg, "Fin · le classement au vidéoprojecteur")
    time.sleep(8)
    mark("end")
    paths = {"staff": st.video.path(), "equipe01": p1.video.path(), "equipe02": p2.video.path()}
    staff_ctx.close(); ctx1.close(); ctx2.close(); b.close()
    json.dump({**paths, "log": log}, open(OUT + "/videos.json", "w"), indent=1)
