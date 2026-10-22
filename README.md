# CTF escape game

An IRL escape game made of CTF challenges: each PC is a **room**, each room is its own CTFd
instance holding one challenge of one or more steps, and groups of lycéens move from room to
room against the clock. One **dashboard** prepares the rooms, lets teams in, shows their timers
and the ranking.

The rooms run the Epitech workshop platform (`Manta-Epitech-Academy/ctfd-workshop-platform`,
inside the `ctfd-custom` image) and their content is imported by that platform's own importer.
See `PLAN.md` for every decision and why.

## Run it

```bash
git clone --recursive https://github.com/kevin-cazal/ctf_escape_game.git
cd ctf_escape_game
cp .env.example .env      # fill it in (see the comments); GPG_PASSPHRASE is given out of band
docker compose up -d --build
```

Everything runs in Docker: the dashboard, one CTFd per room, MariaDB and Redis. Every port listens
on `127.0.0.1` (`BIND_ADDRESS`): put your HTTPS reverse proxy in front, one hostname per room
(ports 9181, 9182…) and one for the dashboard (9180). `deploy/ealab/vhost.sh` is the nginx vhost
used on the test deployment. For a test on one machine without a proxy, use
`ROOMn_URL=http://localhost:918n` and `COOKIE_SECURE=false`.

By default you get **2 rooms, 2 teams and 3 built-in room contents**. On its first start the
dashboard registers the rooms given in `ROOM1_URL`, `ROOM2_URL`… with `ROOMS_ADMIN_TOKEN` (the
admin token every room's CTFd starts with), and creates `equipe01` and `equipe02`.

**More rooms:** copy the `room2` block of `docker-compose.yml` as `room3` and change the 2 to 3
everywhere in it (port variable, secret suffix, database, Redis db, name, volume), add
`room3-uploads` to the volumes at the bottom, and `ROOM3_PORT` / `ROOM3_URL` to `.env`. Each room
creates its own database on first start.

## Use it

1. **Prepare** (before the day): check the rooms, choose a content for each one. In **Room
   contents**, create a content in the editor (steps, text, attachments, flag), or load a
   workshop subject from GitHub (`owner/repo`), any public git URL, or a zip, and export any
   content as a zip. Set the number of teams, **Push**, **Check**, print the team cards.
2. **Live**: a team that clicks « J'ai lu » at a room shows as *waiting*; click **Let in**: its
   timer starts and the room opens on its screen. **Release** lets a team leave a room
   unfinished. If the dashboard is down, staff can type the room code at the PC instead.
3. **Ranking**: most rooms done, then most steps solved in unfinished rooms, then lowest total
   time. **Projector view** (Epitech-branded) for the big screen; **End the game** freezes it.

## Room contents

A room content is a workshop **subject**, reduced to flag steps. The **example zip** linked on the
Prepare page (`dashboard/example/exemple_salle`) has a README with the whole format: one
`## Title` + `<!-- ws: ... -->` marker per step, attachments = the files in `files/<step id>/`,
images in the text anywhere else with a relative path, flags in `flags.yaml` (commit only the
encrypted `flags.yaml.gpg` in a public repository).

`subjects/` holds the 3 built-ins, copied into the dashboard's library on first start: **Agent
064** and **Faux texte** (from `Manta-Epitech-Academy/osint_investigator_ctf_challenges`) and
**Hexadécimal et décimal** (3 steps). Their answers exist only as `*.yaml.gpg`:

```bash
gpg -d subjects/hex_dec/flags.yaml.gpg
gpg -c --cipher-algo AES256 -o subjects/hex_dec/flags.yaml.gpg subjects/hex_dec/flags.yaml
```

## Tools

`tools/record_demo.py` and `tools/record_guide_infra.py` record the demo session and the
infrastructure guide videos (Playwright, then ffmpeg; see their headers).
