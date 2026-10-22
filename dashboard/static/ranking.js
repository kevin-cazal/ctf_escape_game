// The ranking students see on the projector, in the Epitech charter. Same data as the live grid;
// French, since it is for the students.
function showRankingStatus(data) {
  const s = document.getElementById("status");
  if (data.ended_at) { s.textContent = "Terminé"; s.className = "epi-pill over"; }
  else if (data.started_at) { s.textContent = "En direct"; s.className = "epi-pill live"; }
  else { s.textContent = "Bientôt"; s.className = "epi-pill"; }
}

function render(data) {
  showRankingStatus(data);
  document.getElementById("title").textContent = data.ended_at ? "Classement final" : "Classement";
  const n = data.rooms.length;
  const teams = data.ranking.length;
  document.getElementById("summary").textContent =
    `${teams} équipe${teams > 1 ? "s" : ""} · ${n} salle${n > 1 ? "s" : ""}`;
  const roomName = Object.fromEntries(data.rooms.map(r => [r.id, r.name]));
  const board = document.getElementById("ranking");
  if (!data.ranking.length) { board.replaceChildren(el("p", { class: "epi-empty" }, "Les équipes arrivent…")); return; }
  board.replaceChildren(...data.ranking.map(r => {
    const cells = data.grid[r.login] || {};
    const pips = data.rooms.map((room, i) => {
      const c = cells[room.id] || {};
      const state = c.status === "done" ? "done" : c.status === "in" ? "in" : c.status === "paused" ? "paused" : "";
      return el("span", { class: `epi-pip ${state}`, title: room.name }, String(i + 1));
    });
    const scored = r.rooms_done || r.steps_partial;
    const podium = scored && r.rank <= 3 ? ` p${r.rank}` : "";
    const now = !data.ended_at && r.current
      ? el("span", { class: "epi-now" }, "en ce moment : ", el("b", {}, roomName[r.current])) : null;
    return el("div", { class: "epi-row" + podium },
      el("span", { class: "epi-rank" }, scored ? String(r.rank) : "–"),
      el("span", { class: "epi-team" }, teamLabel(r.login), now),
      el("span", { class: "epi-rooms" }, ...pips),
      el("span", { class: "epi-time" }, r.rooms_done ? fmt(r.total_seconds) : "–",
        el("small", {}, `${r.rooms_done}/${n} salle${n > 1 ? "s" : ""}` + (r.steps_partial ? ` · +${r.steps_partial} étape${r.steps_partial > 1 ? "s" : ""}` : ""))));
  }));
}
poll(render);
