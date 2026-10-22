// Shared by the live grid and the ranking: polling, clock offset, time formatting.
const POLL_MS = 3000;
let clockOffset = 0; // server time - browser time, in ms

function fmt(seconds) {
  seconds = Math.max(0, Math.floor(seconds));
  const h = Math.floor(seconds / 3600), m = Math.floor(seconds / 60) % 60, s = seconds % 60;
  const mm = String(m).padStart(2, "0"), ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

function serverNow() { return Date.now() + clockOffset; }

function since(iso) { return (serverNow() - Date.parse(iso)) / 1000; }

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of children) if (c != null) e.append(c);
  return e;
}

function teamLabel(login) { return "Équipe " + login.replace("equipe", ""); }

function showStatus(data) {
  const s = document.getElementById("status");
  if (data.ended_at) { s.textContent = "Game over"; s.className = "status over"; }
  else if (data.started_at) { s.textContent = "Running"; s.className = "status running"; }
  else { s.textContent = "Not started"; s.className = "status"; }
}

async function poll(render) {
  try {
    const r = await fetch("api/results".replace(/^/, "/"), { headers: { Accept: "application/json" } });
    if (r.status === 401) { location.href = "/login?next=" + location.pathname; return; }
    const data = await r.json();
    clockOffset = Date.parse(data.now) - Date.now();
    render(data);
  } catch (e) {
    document.getElementById("status").textContent = "Connection lost, retrying…";
  }
  setTimeout(() => poll(render), POLL_MS);
}
