# CTF Escape Game: POC plan

Repo: `kevin-cazal/ctf_escape_game`, private (20/10), then **public** for the POC delivery
(22/10), as a single snapshot commit: the earlier history held the built-ins' answers.

**Status 20/10: POC built and running** on https://dashboard.eg.ealab.duckdns.org, today with
the default event (22/10): 2 rooms (https://room1.eg.ealab.duckdns.org, room2), 2 teams. Checked end to end in a browser: push,
health check, "Let in", a team solving its room (time and wrong answers on the grid), the guard
refusing a team still in another room, the room code typed at the PC, the ranking, swapping a
room's content and back, reset.

## Goal

Prove the escape-game format from the meeting of 15/10/26 (Strasbourg) before the event of
12/11/26: groups of lycéens move from PC to PC, each PC is a "room" with one challenge, staff see
every group's progress and time on one dashboard.

POC due: end of week of 19/10. Check-in with Kevin Spegt around 22/10.

## Decisions

| Topic | Decision | Why |
|---|---|---|
| Instances | 1 room = 1 CTFd instance | Specific to this use case, decided in the meeting |
| Team identity | Same login in every instance (`equipe01`, `equipe02`...), created before the event, given on a card | One string links a group across rooms; no typos, no duplicates, no unwanted names |
| Team mode | CTFd user mode, one shared account per group | The group plays at one PC; team mode means N accounts per student for nothing |
| Room entry | A door step before the room challenge. Staff open it from the dashboard ("authorize"), which creates the team's door solve (decided 20/10). With the plugin the door is a `checkpoint` step, so a room code exists as a fallback (to confirm) | Staff decide when the clock starts |
| One room at a time | The dashboard refuses to authorize a team that is still inside another room (staff can force it) | Stops a group from playing two rooms at once |
| Ranking | Most rooms done, then most steps solved in rooms not finished, then lowest total time of the rooms done (decided 21/10; was rooms then time) | Rewards partial work in long rooms without changing what "done" means |
| Rooms | 5 for the POC (decided 20/10); Rex stays in the catalog as a spare | |
| Time in a room | Solve time of the room challenge minus solve time of the door | Both are standard CTFd solves |
| Concept quizzes | Not used | Decided 20/10 |
| Workshop plugin | **Reused as much as possible** (user, 20/10): every room runs `ghcr.io/manta-epitech-academy/ctfd-custom` (CTFd + the plugin from `Manta-Epitech-Academy/ctfd-workshop-platform`). See "Reuse of the workshop platform" | No re-invented wheel |
| Flags in the repo | GPG-encrypted only (`private/flag.txt.gpg`). The dashboard decrypts them at push time with `GPG_PASSPHRASE` from `.env` | The repo is private, but this keeps it safe to share or publish later |

## Rooms (POC)

All from `osint_investigator_ctf_challenges` (copied into this repo, flags kept encrypted).

| Room | Theme | Challenge | Source folder | Tier |
|---|---|---|---|---|
| 1 | Encodage | Agent 064 | `challenges/cryptography/agent_064` | 2 |
| 2 | Encodage | Hexadécimal et décimal (3 steps, from scratch, 21/10) | `subjects/hex_dec` | 2 |
| 3 | Stéganographie | Tarte aux fraises | `challenges/steganography/tarte_aux_fraises` | 2 |
| 4 | Forensics | Faux texte | `challenges/steganography/faux_texte` | 3 |
| 5 | GEOINT | Un simple pont | `challenges/geoint/un_simple_pont` | 3 |
| (6) | Programmation | Rex | `challenges/programming/rex` | 3 |

Their `requirements: Tutoriel` is replaced by the door of their room.

## What one room contains

(Built by the plugin's importer from the room's subject.)

1. The intro (`__intro__`) and index page: the room's welcome text.
2. Door: a `checkpoint` step. Solved by the dashboard for one team when staff let it in (or by
   the room code typed at the PC).
3. The room challenge: a `flag` step, after the door.
4. The accounts `equipe01..NN`, same passwords as in every other room.
5. Registration closed, scoreboard hidden (the dashboard replaces it).

Decided 20/10: the dashboard does not start containers. It is given existing instances.

## Deployment: Docker only

Decided 20/10. The POC is built and run exclusively with Docker / Docker Compose. The deliverable
is a `docker-compose.yml` that the client can deploy anywhere, with no other install.

- Every part runs as a container: the dashboard, and one stock CTFd service per room, all in the
  same compose (decided 20/10). Compose cannot loop, so rooms are listed one by one (`room1`,
  `room2`...); adding a room = copying one service block and its volume.
- HTTPS is left to the client's own reverse proxy (decided 20/10). The compose only publishes
  plain HTTP ports, one per room and one for the dashboard, set in `.env`.
- The room image is built from `Manta-Epitech-Academy/ctfd-custom` at a pinned commit, straight
  from its public git repo (`build: context: https://github.com/...#<sha>`): the published
  `ghcr.io/manta-epitech-academy/ctfd-custom` needs an organisation login. The dashboard image is
  built from this repo. Publishing both to a registry, so a client builds nothing, is later work.
- Everything the client sets goes in one `.env` (ports, staff password, number of rooms).
- Persistent data in named volumes (dashboard state, each CTFd's database and uploads).
- No host-side scripts. Any helper runs inside a container (`docker compose run ...`).

### No setup wizard, no hand-made token (stock CTFd 3.8.5, verified)

CTFd reads these from environment variables (`[management]` in `CTFd/config.ini`, env
overrides the file through `EnvInterpolation`):

- `PRESET_ADMIN_NAME`, `PRESET_ADMIN_EMAIL`, `PRESET_ADMIN_PASSWORD`: the admin account
- `PRESET_ADMIN_TOKEN`: an API token the client chooses; the first API call with it creates the
  preset admin (`CTFd/utils/security/auth.py`, `lookup_user_token`)
- `PRESET_CONFIGS`: JSON configs that win over the database, e.g. `{"setup": true,
  "ctf_name": "...", "registration_visibility": "private", "score_visibility": "hidden"}`

So each CTFd service in the compose comes up set up, with an admin token known in advance. The
token the client puts in `.env` is the one they give the dashboard with the instance URL.

## POC target: ealab.duckdns.org

Decided 20/10. The POC runs on `ssh debian@ealab.duckdns.org` (51.91.78.164, passwordless sudo),
never on localhost. Only public URLs are used and reported, including the instance URLs given
to the dashboard.

| Service | Public URL | Host port (127.0.0.1 only) |
|---|---|---|
| Dashboard | https://dashboard.eg.ealab.duckdns.org | 9180 |
| Room 1..N | https://room1.eg.ealab.duckdns.org ... roomN | 9181..918N |

Checked on the server 20/10:
- DuckDNS resolves `*.eg.ealab.duckdns.org` to the server (wildcard at any depth).
- Docker 28.5, Compose 2.39. 6 CPU, 11 GiB RAM (6.8 available), 21 GB disk free.
- Ports in use: 22 25 53 80 443 4242 5355 8000 8001 8080 9000 9001 9080-9090. The 918x range
  is free.
- The box is shared: the workshop platform (`*.ealab.duckdns.org`, `self.*`), back2epitech, older
  CTFd stacks, and the bare `ealab.duckdns.org` site. Nothing of theirs may be touched.

HTTPS: the host nginx + certbot already on the server plays the "client's reverse proxy". One
vhost and one certificate per name, like the existing instances. These vhost files are server
config, not part of the deliverable; the README shows one as an example for clients.

All rooms share one MariaDB (one database per room) and one Redis (one db number per room).

Server-specific: Docker's default address pools are used up on this box, so
`deploy/ealab/docker-compose.override.yml` gives the stack its own subnet (10.209.0.0/24). The
nginx vhosts are written by `deploy/ealab/vhost.sh`. Code lives in `/srv/ctf_escape_game`.

## Repo layout

```
challenges/<name>/       ctfcli challenge dirs to choose rooms from (challenge.yml, files, private/*.gpg)
docker-compose.yml       the deliverable: dashboard + CTFd instances
.env.example             what the client sets
dashboard/               the staff dashboard (small backend + UI; it stores the instance list
                         and tokens, and must sit behind a staff login)
```

Changing a room = picking another challenge in the dashboard and pushing again.

## Dashboard: the one tool for the whole event

The dashboard holds everything. The CTFd instances are only where students play; staff never need
the CTFd admin pages. It talks to every instance through the CTFd API with an admin token, from
its server side (CTFd has no CORS, and the tokens must not reach the browser).

Three phases:

### 1. Before the day: prepare

- Start: an empty dashboard asks for a CTFd instance URL and its admin token. Staff add one
  instance per room. On add, the dashboard checks the token is an admin one (an admin-only call
  such as `GET /api/v1/configs`) and shows the instance as ready or not.
- URLs given to the dashboard are the public ones (`https://roomN.eg.ealab.duckdns.org`).
- The instance must already exist and be set up. With the compose, the `PRESET_*` variables do
  that (see Deployment). Starting containers is not the dashboard's job.
- Choose the challenge of each room (swap = pick another challenge dir)
- Create the teams: number of teams, generate logins and passwords
- Push to every instance: setup, accounts, door, challenge
- Health check: every instance up, every room has its door and challenge, every team can log in
- Print the team cards (login + password)
- Reset: wipe solves after a rehearsal

### 2. During: monitor and authorize

- Grid: one row per team, one column per room. A cell is "not entered", "in the room" (live
  timer) or "done" (time spent)
- Authorize: staff let a team into a room from the dashboard. Technically this creates the
  team's door solve in that instance (`POST /api/v1/submissions`, admin only, native CTFd). The
  timer starts at that moment.
- Data: `GET /api/v1/submissions?type=correct` from every instance, polled every few seconds

### 3. During and after: ranking

- Live ranking during the game, final ranking after it
- Rule (to confirm): most rooms done first, then lowest total time
- A screen-friendly view for a projector

## Out of scope for the POC

- Auto-logout of the previous group at a shared PC (staff check it by hand)
- Stopping a group from playing two rooms at once on phones (staff hand out codes in person)
- Production hosting, HTTPS, more than one event at a time
- Starting or stopping CTFd containers from the dashboard

## The room opens on the student's screen by itself (20/10)

"Let in" used to need a manual reload on the student's PC. Now:

- At push, the dashboard writes a small script into the room's **theme footer** (Admin > Config >
  Theme footer: CTFd's own extension point, injected on every page by `base.html`; no plugin
  change). Between `<!-- escape-game:door -->` markers, so anything else in the footer is kept.
- While the door step is on the page and not done, the script asks CTFd for the team's own solves
  (`/api/v1/users/me/solves`) every 3 s. When the door is among them it shows "La salle est
  ouverte, c'est parti !" and reloads: the challenge is then open with its answer field ready.
  Measured: toast 2.8 s after the click, page ready 4.9 s after.
- "Let in" also solves the welcome step ("J'ai lu") when the team skipped it, since the door
  requires it: otherwise the room opened behind a door still drawn locked.
- **Waiting teams** (20/10): a team that clicks « J'ai lu » at a room it is not let into yet is
  *waiting* there. The live grid paints that cell blue with a "Let in" button and how long it has
  waited, and a bar above the grid lists every waiting team, oldest first, each with its own
  "Let in". A team waits in one room at most (its latest « J'ai lu ») and never while it is
  inside another room. The welcome text asks for the click: "Clique sur « J'ai lu » :
  l'encadrant voit que ton équipe attend devant cette salle."
- The clean version, later: the plugin's page could watch for unlocks itself (it already
  patches steps in place after a solve, `refresh()` in `workshop_page.js`, but never polls).
  That is a plugin PR; the footer script is the no-change version of it.

## Rooms with several steps, and Release (21/10)

A room can hold several challenge steps in a fixed order, each unlocking the next (the
subject's chapter is `topology: linear`: door, then step 1, step 2...). The platform needed
nothing for it; the dashboard now reads every step of the room's subject.

- Grid: a room in progress shows its timer and `solved/total` (only when there are 2+ steps).
  It is done when the last step is solved. Room time = last step - door, minus released time.
- **Release** (in-room cell, once a step is solved; before that it is "cancel"): the team leaves
  the room unfinished. Its steps stay solved, its clock for that room stops, the cell turns grey
  "released" with the frozen time, and "Let in" later resumes the clock where it stopped. The
  pauses live in the dashboard's state (`pauses`), not in CTFd: the door stays open in CTFd, so a
  released team could still answer from its own device; staff trust, as with the room codes.
- Text between steps ("ce que tu viens d'apprendre te servira"): not now (user, 21/10).

**Salle 2, "Hexadécimal et décimal"** (`subjects/hex_dec`), written from scratch at the user's
request (21/10): 1. a word in hexadecimal with `0x` prefixes, 2. a word in decimal, 3. a
sentence where each character is either (a single word mixes both, the `0x` tells which).
Flags case-insensitive, `ctf{...}`. Played end to end with a release in the
middle: 3/3 in 136 s with the released time left out.

## Room contents: load, create, edit, bind (22/10)

The Prepare tab has a **Room contents** library. A content = 1-N steps, each with a title, a
description (markdown), 0-N attachments and one flag (case-insensitive by default), plus the room
code. Decisions (user, 22/10):

- **Load** a workshop **subject** (the platform's convention, `subject.yaml` at the root; or in
  its one top-level folder, as in a "Download ZIP") from (22/10):
  - `owner/repo`: GitHub, with the plugin's own fetcher (`source.py` `materialize`, public);
  - an `http(s)://` git URL, any host (GitLab, Bitbucket, self-hosted): `git clone --depth 1`,
    http(s) only, no credential prompt, no submodules, 2 minutes at most;
  - an uploaded `.zip` (paths that leave the archive, symlinks and more than 200 MB refused).
  Every step must be a `flag` step; a subject with checkpoint, quiz or token steps is refused
  with their list. Its welcome page is replaced by the room's; hints are kept (not editable).
  Encrypted answers open with `GPG_PASSPHRASE`; a flag that does not open stays empty and the
  content is "not ready" until it is typed in the editor.
- **Example zip** (link under "Load a workshop subject", 22/10): `dashboard/example/exemple_salle`
  zipped on the fly: a 2-step room with an attachment (`files/etape1/indice.txt`), an image in
  the text (`img/canard.png`), a hint, plaintext `flags.yaml`, and a README that explains the
  format (steps, files, images in the text, flags and their encryption).
- **Attachments, "Option 1"** (22/10): a step's attachments are all the files in
  `files/<step id>/` (the `id` of its `ws:` marker). No `attachments.yaml`, no hand-written
  download links: the dashboard adds the "Fichiers à télécharger" block and an inline view of
  image attachments at push time (and generates an internal `attachments.yaml` for its upload).
  The old form is not read any more; the 3 built-ins were converted, and their push output was
  checked byte for byte against the old form's. Export writes the new form.
- **Images in the text**: anywhere outside `files/`, shown with a markdown image whose path is
  relative to the `.md`. The library keeps them (`assets/<path>`) and writes them back at the
  same path, for a push (the platform uploads them) and for an export.
- Checked on ealab 22/10: the example zip, downloaded from the dashboard and loaded back, gave 2
  steps, `indice.txt` as step 1's attachment and the duck in its text; bound to Salle 1 and
  pushed, a team saw the duck (240x200, served from the room's `/files/`) and downloaded
  `indice.txt`. Salle 1 put back to Agent 064, test answers and test content deleted.
- **Export as zip** (library table and editor): the content as a subject, answers only as
  `*.yaml.gpg`. It loads back with "from a zip file", and can be committed as a subject repo.
- **Create**: the same editor, from scratch. Steps can be added, removed, moved. Attachments
  add up (each "+ Add files" or drop adds to the list, × removes one). A `#` or `##` title typed
  in a description is silently turned into `###` (outside code blocks), since levels 1 and 2
  are the room and its steps on the student page.
- **Storage**: the dashboard's data volume, `/data/contents/<id>/` (`model.json`, files, and
  `secrets.json.gpg` holding flags and room code, encrypted with `GPG_PASSPHRASE`).
- **Built-ins** (`subjects/` in this repo) are copied into the library on first start and are
  then editable like the rest; a redeploy never overwrites an edited one.
- **Binding**: each room's content dropdown (step 1 of Prepare) lists the library; contents not
  ready are disabled. A content in use cannot be deleted. Edits apply at the next push.
- At push, `library.build_subject` writes the content as a subject (welcome page, `porte` door,
  one flag step per step, attachments with the platform's location scheme) and the platform's
  importer takes it from there. Built-ins round-trip to the same markdown and file locations, so
  rooms keep their step ids and their results.

Checked 22/10 on ealab: the 7 built-ins seeded and pushed to the 5 rooms; a 2-step content created
in the browser (attachment upload, a missing flag reported, then saved), bound to Salle 5, played
by a team (attachment downloaded, 2/2 done), then Salle 5 put back; `kevin-cazal/shell-1_subject`
loaded with its 42 flags; `pypong_subject` and `tortue_subject` refused (quiz and checkpoint steps).
Test contents deleted afterwards.

## Default configuration (22/10)

A fresh `docker compose up` gives **2 rooms, 2 teams and 3 built-in room contents**:

- `docker-compose.yml` runs `room1` and `room2` (rooms 3 and up: copy a block, see its header).
- Built-ins in `subjects/`: **Agent 064** (1 step), **Hexadécimal et décimal** (3 steps), and
  **Faux texte** (1 step, a file and hints) as a spare. The other converted OSINT challenges
  (Plat de résistance, Tarte aux fraises, Un simple pont, Rex) left the repo; they stay in git
  history and in their source repo, and load back as zips or from git.
- On its very first start (no state file yet) the dashboard creates `equipe01` and `equipe02`,
  and registers the rooms named in `ROOM1_URL`, `ROOM2_URL` (`.env`) with `ROOMS_ADMIN_TOKEN`,
  Salle 1 with Agent 064 and Salle 2 with Hexadécimal et décimal. Staff then only Push and
  Check. Never again after that: the state is the staff's.
- ealab was reset to it on 22/10 (all volumes wiped, rooms 3-5 and their vhosts and certificates
  removed): first start registered Salle 1 (Agent 064) and Salle 2 (Hexadécimal et décimal) and
  created 2 teams; push and health check all green.

## Reuse of the workshop platform

Source of truth: `Manta-Epitech-Academy/ctfd-workshop-platform` main (7ec7c25 on 20/10).

| Need | Reused from the platform | New |
|---|---|---|
| CTFd + plugin per room | image `ghcr.io/manta-epitech-academy/ctfd-custom`, its compose pattern, `PRESET_ADMIN_*` | the 5-room compose |
| Room content | the subject convention (`docs/CONTENT_CONVENTION.md`); one subject per room, made from the ctfcli challenge with `CTF_deployments/tools/ctf2subject.py` | `--only <challenge>` option in the converter (or hand-written subjects) |
| Pushing content | the plugin's importer `tools/sync_subject.py`, unchanged, token auth (`CTFdAdmin(url, token=)`) | the dashboard calls it per room |
| Flags | `flags.yaml.gpg` sidecar, same GPG scheme as the `*_subject` repos | the dashboard decrypts with `GPG_PASSPHRASE` before calling the importer |
| Room door | a `checkpoint` step (instructor-led mode): the room's code, chosen in `checkpoint_codes.yaml`, gates the flag step | "Let in" in the dashboard = the team's checkpoint solve (`POST /api/v1/submissions`). The code stays as a fallback staff can type at the PC |
| Participant page | `/workshop` single-page view: intro, door, challenge, hints, flag box | nothing |
| Per-room deep dive | `/admin/workshop/stats`, `/admin/workshop/submissions` on each instance | links from the dashboard |
| Accounts | none in the plugin (no bulk creation) | the dashboard creates them with core `POST /api/v1/users` |
| Live status, timers, ranking | none in the plugin (no cross-instance view, no timing) | the dashboard, reading core `/api/v1/submissions` |

No plugin change is needed for the POC. Candidates for a later upstream PR: a JSON endpoint of
per-participant status (`answers.py` `_attendees()`), bulk account creation.

Why the dashboard runs the importer instead of the in-instance sync page: the sync page only
fetches **public** GitHub repos, one repo per instance (`source.py`), and waits for a browser to
decrypt the answers. The importer it runs is the same `sync_subject.py`, so calling it directly
changes nothing in what gets imported.

## Deferred: the dashboard as the admin interface of each room (asked 20/10, deferred 20/10)

For ease of use, staff should never have to open a room's CTFd admin separately: the dashboard
shows each room's admin pages (CTFd admin, `/admin/workshop/stats`, `/admin/workshop/submissions`)
inside it, in an iframe that is already logged in.

What makes it possible, and what is left to decide:

- Framing: the room vhosts send no `X-Frame-Options` and CTFd sets none, so the pages can be
  framed. A `Content-Security-Policy: frame-ancestors` naming the dashboard would allow exactly
  that and nothing else.
- Cookies: `dashboard.eg...` and `roomN.eg...` are the same site (`duckdns.org` is a public
  suffix, so the site is `ealab.duckdns.org`), so CTFd's session cookie works inside the iframe.
  On a client domain the same holds as long as dashboard and rooms share one registrable domain.
- Logged in: CTFd admin pages need a session cookie, set by the room's own host. The admin
  token cannot be used for that directly:
  - CTFd only reads a token on JSON API calls (and file uploads), never on a page load;
  - the dashboard cannot send it from the browser either: CTFd has no CORS, and the token must
    not reach the browser anyway;
  - a session the dashboard opens server-side (a token API call does log in, CTFd
    `utils/initialization` `tokens()`) cannot be handed over: only the room's host can set a
    cookie for the room.
- **Decision (user, 20/10): use the admin token the dashboard already has.** Design: a
  one-time ticket signed with the room's admin token.
  1. The dashboard builds `b64url(claims) . b64url(HMAC(key, part1))`, with
     `key = HMAC(PRESET_ADMIN_TOKEN, "escape-game/admin")`, and claims `{next, iat, exp = iat + 60,
     jti}`. The token itself never leaves the server.
  2. The iframe opens `https://roomN.../admin/workshop/enter?t=<ticket>`.
  3. A small route in the workshop plugin checks the signature with its own `PRESET_ADMIN_TOKEN`,
     the expiry and single use, logs the browser in as the preset admin (`login_user`), and
     redirects to `next` (only paths under `/admin`).
  Reused from `jump.py`: `derived_key`, the b64url ticket format and its checks, `burn_jti`
  (atomic single use on the cache). Nothing new to configure: the shared secret is the token.
  Cost: a plugin change, so a PR to `Manta-Epitech-Academy/ctfd-workshop-platform`, then a bump
  of the `ctfd-custom` commit the compose pins.
- Fallback until that PR is merged: staff log into each room once inside the iframe.
- Rejected: the dashboard proxying each room's admin under its own origin (it would have to
  rewrite CTFd's links and its CSRF nonces).

## The Epitech graphical charter on the ranking (asked 20/10, built 22/10 for the ranking)

The dashboard must look like an Epitech product, like the rooms do. Take it from the two places
that already apply the charter, do not pick values by eye:

- `Manta-Epitech-Academy/jump`, `DESIGN.md`: the visual contract derived from the official
  Epitech charte graphique, and its implementation `frontend/src/routes/layout.css`.
- `Manta-Epitech-Academy/ctfd-workshop-platform`, `DESIGN.md` and
  `plugins/workshop/assets/epitech-theme.css`: the same tokens ported to CTFd, which is what the
  students see in each room.

What to reuse (already in the platform, so in the room image):

- Colours: `epi-blue #013afb` (brand surfaces, never changes, it is the logo), `epi-tech #00ff97`,
  `epi-together #ff5f3a`, chrome `#0b0e1a`; the semantic roles with their light and dark values
  (primary, success = tech ink `#007a46`, danger = together ink `#b5361a`, warning `#8a5a00`,
  background `#f6f7fb`, card `#fff`, border `#d9dce8`, muted text `#555b71`).
- Typography: Anton for display titles, IBM Plex Sans for text, Space Mono for codes and timers.
  Self-hosted woff2 files from `plugins/workshop/assets/fonts/` (with their LICENSE.md), never a
  font CDN: school wifi cannot be trusted.
- The logo: `plugins/workshop/assets/brand/EPITECH-LOGO-{BLANC,BLEU}-2025.svg`.
- The patterns students already know from the room page: the blue band header with the Anton
  title, the progress pill, the card style.

Built 22/10 on the ranking, the page non-staff see (`/ranking?screen=1` on the projector; the
staff Ranking tab shows the same board, smaller): the blue band with the blueprint grid and the
pixel squares, the white 2025 logo, an Anton `CLASSEMENT_` title with the tech-green cursor, a
status pill (Bientôt / En direct / Terminé), then one card per team: Anton rank, team, a square
per room (tech green = done, blue outline pulsing = in the room), Space Mono time. The leader's
card is brand blue, 2nd and 3rd are outlined in it. French, for the students. Styles in
`dashboard/static/epitech.css`; fonts and logo copied from the submodule at build time. The staff
pages (Prepare, Live) keep their own look for now.

How: copy the assets from the `vendor/ctfd-workshop-platform` submodule at build time (not a
second copy in this repo), and port the tokens into the dashboard's `style.css` as CSS variables
with the same names as the platform's `--epi-*`. Light theme first; dark only if the projector view
needs it. The ranking projector view is the most visible screen: it gets the band and the logo.

## Content notes

- Faux texte: the source lists three files, but `ctf_numbers.png` and `ctf_numbers_encrypt.txt`
  are the same unrelated image (a card number, from another challenge). Only `txtfake.txt` is the
  challenge, so only it is shipped.
- The `requirements: Tutoriel` of every source challenge is dropped; the door replaces it.

## Open

- Number of teams and team size for 12/11

