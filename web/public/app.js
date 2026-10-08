const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("msg");
const send = document.getElementById("send");
const statusEl = document.getElementById("status");

function bubble(text, cls, meta) {
  const div = document.createElement("div");
  div.className = "bubble " + cls;
  div.textContent = text;
  if (meta) {
    const m = document.createElement("div");
    m.className = "meta";
    m.textContent = meta;
    div.appendChild(m);
  }
  chat.appendChild(div);
  div.scrollIntoView({ behavior: "smooth", block: "end" });
  return div;
}

async function refreshStatus() {
  try {
    const r = await fetch("/api/health/ready");
    const j = await r.json();
    statusEl.className = "status " + (r.ok ? "ok" : "ko");
    statusEl.textContent = r.ok ? "API, base de données et LLM opérationnels" : "Service dégradé : " + JSON.stringify(j);
  } catch (e) {
    statusEl.className = "status ko";
    statusEl.textContent = "API injoignable";
  }
}

async function refreshHistory() {
  try {
    const r = await fetch("/api/history?limit=10");
    const rows = await r.json();
    const ol = document.getElementById("history");
    ol.innerHTML = "";
    rows.forEach((row) => {
      const li = document.createElement("li");
      li.textContent = `#${row.id} — ${row.prompt} (${row.latency_ms} ms, ${row.tokens} tokens)`;
      ol.appendChild(li);
    });
  } catch (e) { /* ignoré */ }
}

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  bubble(message, "user");
  input.value = "";
  send.disabled = true;
  const waiting = bubble("…", "bot");
  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const j = await r.json();
    waiting.remove();
    bubble(j.answer, "bot", `${j.model} · ${j.latency_ms} ms · ${j.tokens} tokens`);
    refreshHistory();
  } catch (e) {
    waiting.textContent = "Erreur : " + e.message;
  } finally {
    send.disabled = false;
    input.focus();
  }
});

refreshStatus();
refreshHistory();
setInterval(refreshStatus, 15000);
