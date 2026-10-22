// Live grid: one row per team, one column per room. Cells tick every second between polls.
let last = null;

async function send(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { status: r.status, data: await r.json().catch(() => ({})) };
}

async function letIn(room, login, roomName) {
  let res = await send("/api/authorize", { room, login });
  if (res.status === 409 && res.data.busy) {
    if (!confirm(`${res.data.error}\nLet ${teamLabel(login)} into ${roomName} anyway?`)) return;
    res = await send("/api/authorize", { room, login, force: true });
  }
  if (res.status !== 200) alert(res.data.error || "Failed.");
  refreshSoon();
}

async function cancel(room, login, roomName) {
  if (!confirm(`Cancel ${teamLabel(login)}'s entry into ${roomName}? Its timer is erased.`)) return;
  const res = await send("/api/cancel", { room, login });
  if (res.status !== 200) alert(res.data.error || "Failed.");
  refreshSoon();
}

let soon = null;
function refreshSoon() {
  clearTimeout(soon);
  soon = setTimeout(async () => {
    const r = await fetch("/api/results");
    if (r.ok) { const d = await r.json(); clockOffset = Date.parse(d.now) - Date.now(); render(d); }
  }, 200);
}

async function release(room, login, roomName) {
  if (!confirm(`Release ${teamLabel(login)} from ${roomName}? Its solved steps are kept and its timer stops; Let in later resumes it.`)) return;
  const res = await send("/api/release", { room, login });
  if (res.status !== 200) alert(res.data.error || "Failed.");
  refreshSoon();
}

function steps(c) { return c.total > 1 ? el("span", { class: "steps" }, `${c.solved}/${c.total}`) : null; }

function cell(data, room, login) {
  const c = data.grid[login][room.id];
  if (!c) return el("td", { class: "c-err" }, "?");
  const fails = c.fails ? el("span", { class: "fails" }, `${c.fails} wrong`) : null;
  if (c.status === "done")
    return el("td", { class: "c-done" }, el("span", { class: "time" }, fmt(c.seconds)), fails);
  if (c.status === "in")
    return el("td", { class: "c-in" },
      el("span", { class: "time tick", "data-since": c.clock_from }, fmt(since(c.clock_from))), " ", steps(c), fails,
      el("span", { class: "acts" },
        c.solved
          ? el("button", { class: "link small", title: "The team leaves; steps kept, timer stops", onclick: () => release(room.id, login, room.name) }, "release")
          : el("button", { class: "link small", title: "Cancel this entry", onclick: () => cancel(room.id, login, room.name) }, "cancel")));
  if (c.status === "paused")
    return el("td", { class: "c-paused" },
      el("span", { class: "time" }, fmt(c.seconds)), " ", steps(c),
      el("span", { class: "fails" }, "released"),
      data.ended_at ? null : el("button", { class: "letin", onclick: () => letIn(room.id, login, room.name) }, "Let in"));
  if (data.ended_at) return el("td", { class: "c-out" }, "–");
  if (c.status === "waiting")
    return el("td", { class: "c-wait" },
      el("button", { class: "letin primary", onclick: () => letIn(room.id, login, room.name) }, "Let in"),
      el("span", { class: "waited tick", "data-since": c.waiting_since, title: "Waiting since it clicked « J'ai lu »" },
        fmt(since(c.waiting_since))));
  return el("td", { class: "c-out" },
    el("button", { class: "letin", onclick: () => letIn(room.id, login, room.name) }, "Let in"));
}

function render(data) {
  last = data;
  showStatus(data);
  const errs = document.getElementById("errors");
  errs.replaceChildren(...Object.entries(data.errors).map(([id, msg]) => {
    const room = data.rooms.find(r => r.id === id);
    return el("div", { class: "flash error" }, `${room ? room.name : id}: ${msg}`);
  }));
  renderWaiting(data);
  const grid = document.getElementById("grid");
  document.getElementById("empty").hidden = data.rooms.length > 0;
  if (!data.rooms.length) { grid.replaceChildren(); return; }
  const rankOf = Object.fromEntries(data.ranking.map(r => [r.login, r]));
  const head = el("tr", {}, el("th", {}, "Team"),
    ...data.rooms.map(r => el("th", {}, r.name,
      el("small", {}, (r.challenge || "") + (r.steps > 1 ? ` · ${r.steps} steps` : "")))),
    el("th", {}, "Done"));
  const rows = Object.keys(data.grid).map(login =>
    el("tr", {}, el("th", { class: "team" }, teamLabel(login)),
      ...data.rooms.map(r => cell(data, r, login)),
      el("td", { class: "total" }, `${rankOf[login].rooms_done}/${data.rooms.length}`)));
  grid.replaceChildren(el("thead", {}, head), el("tbody", {}, ...rows));
}

// Teams sitting at a room, waiting to be let in: the first thing staff need, so on top.
function renderWaiting(data) {
  const box = document.getElementById("waiting");
  const items = [];
  for (const [login, cells] of Object.entries(data.grid))
    for (const room of data.rooms) {
      const c = cells[room.id];
      if (c && c.status === "waiting") items.push({ login, room, since: c.waiting_since });
    }
  items.sort((a, b) => a.since.localeCompare(b.since));
  box.hidden = !items.length || !!data.ended_at;
  box.replaceChildren(
    el("span", { class: "wtitle" }, items.length === 1 ? "1 team waiting" : `${items.length} teams waiting`),
    ...items.map(w => el("span", { class: "wteam" },
      el("b", {}, teamLabel(w.login)), ` at ${w.room.name} · `,
      el("span", { class: "tick", "data-since": w.since }, fmt(since(w.since))), " ",
      el("button", { class: "letin primary", onclick: () => letIn(w.room.id, w.login, w.room.name) }, "Let in"))));
}

setInterval(() => {
  for (const t of document.querySelectorAll(".tick")) t.textContent = fmt(since(t.dataset.since));
}, 1000);

poll(render);
