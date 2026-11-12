// Prueba local del Worker: D1 simulado con node:sqlite y fetch externo simulado.
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import worker, { adminToken, webhookSecret, resolveOrigin, dispatchSearch } from "./dist/worker.mjs";

const db = new DatabaseSync(":memory:");
db.exec(readFileSync(new URL("../schema.sql", import.meta.url), "utf8"));
const D1 = {
  prepare(sql) {
    let args = [];
    const st = db.prepare(sql);
    const o = {
      bind: (...a) => ((args = a.map((x) => (x === undefined ? null : x))), o),
      first: async () => st.get(...args) ?? null,
      all: async () => ({ results: st.all(...args) }),
      run: async () => { const r = st.run(...args); return { meta: { changes: Number(r.changes) } }; },
    };
    return o;
  },
};

const sent = []; // mensajes enviados a Telegram / Resend
const PLACES = {
  madrid: [{ code: "MAD", name: "Madrid", country_name: "España", country_code: "ES" }],
  mad: [{ code: "MAD", name: "Madrid", country_name: "España", country_code: "ES" }],
  liberia: [{ code: "LIR", name: "Liberia", country_name: "Costa Rica", country_code: "CR" }],
  miami: [{ code: "MIA", name: "Miami", country_name: "Estados Unidos", country_code: "US" }],
};
globalThis.fetch = async (input, init = {}) => {
  const url = typeof input === "string" ? input : input.toString();
  if (url.includes("autocomplete.travelpayouts.com")) {
    const term = new URL(url).searchParams.get("term").toLowerCase();
    return new Response(JSON.stringify(PLACES[term] || []));
  }
  if (url.includes("api.telegram.org") || url.includes("api.resend.com") || url.includes("api.github.com")) {
    sent.push({ url, body: JSON.parse(init.body) });
    return new Response(JSON.stringify({ ok: true }));
  }
  throw new Error("fetch inesperado " + url);
};

const env = {
  DB: D1, TELEGRAM_BOT_TOKEN: "123:ABC", RESEND_API_KEY: "re_x",
  SITE_URL: "https://buscavuelosbaratos.com", API_URL: "https://api.buscavuelosbaratos.com",
  MAIL_FROM: "Busca Vuelos Baratos <alertas@buscavuelosbaratos.com>",
};
const secret = await webhookSecret(env);
const call = (path, opt = {}) => worker.fetch(new Request("https://api.buscavuelosbaratos.com" + path, opt), env);
const tgSay = async (text, chat = 555) => {
  sent.length = 0;
  const r = await call("/telegram", {
    method: "POST", headers: { "X-Telegram-Bot-Api-Secret-Token": secret, "Content-Type": "application/json" },
    body: JSON.stringify({ message: { text, chat: { id: chat, type: "private" } } }),
  });
  assert.equal(r.status, 200);
  return sent.map((s) => s.body.text || "").join("\n---\n");
};
const subs = () => db.prepare("SELECT channel,address,origin,destination,status FROM subscriptions ORDER BY id").all();

// Resolución de orígenes
assert.deepEqual(resolveOrigin("sjo"), { code: "SJO" });
assert.deepEqual(resolveOrigin("San Jose"), { code: "SJO" });
assert.deepEqual(resolveOrigin("Costa Rica"), { choices: ["SJO", "LIR"] });
assert.deepEqual(resolveOrigin("panamá"), { code: "PTY" });
assert.equal(resolveOrigin("Madrid"), null);

// Webhook sin secreto → 403
assert.equal((await call("/telegram", { method: "POST", body: "{}" })).status, 403);

// Flujo guiado
assert.match(await tgSay("/start"), /Busca Vuelos Baratos/);
assert.match(await tgSay("/alerta"), /Desde qué ciudad/);
assert.match(await tgSay("Costa Rica"), /Desde cuál ciudad/);
assert.match(await tgSay("San José (SJO)"), /A qué ciudad/);
assert.match(await tgSay("Liberia"), /internacionales/);           // nacional: rechazado
assert.match(await tgSay("Madrid"), /Alerta creada[\s\S]*San José → Madrid/);
// Comando directo
assert.match(await tgSay("/alerta Bogotá a Miami"), /Alerta creada[\s\S]*Bogotá → Miami/);
assert.match(await tgSay("/alerta SJO MAD"), /Ya tenías esta alerta/);
assert.equal(subs().filter((s) => s.status === "active").length, 2);

// Listar y quitar con botón
await tgSay("/misalertas");
const kb = sent[0].body.reply_markup.inline_keyboard;
assert.equal(kb.length, 2);
sent.length = 0;
await call("/telegram", {
  method: "POST", headers: { "X-Telegram-Bot-Api-Secret-Token": secret },
  body: JSON.stringify({ callback_query: { id: "q1", data: kb[0][0].callback_data, message: { message_id: 9, chat: { id: 555 } } } }),
});
assert.equal(subs().filter((s) => s.status === "active").length, 1);

// Formulario web por correo
const post = (b) => call("/api/subscribe", { method: "POST", headers: { Origin: env.SITE_URL, "Content-Type": "application/json" }, body: JSON.stringify(b) });
let r = await post({ email: "malo", origin: "SJO", destination: "Madrid" });
assert.equal(r.status, 400);
r = await post({ email: "ana@example.com", origin: "SJO", destination: "Liberia" });
assert.match((await r.json()).error, /internacionales/);
sent.length = 0;
r = await post({ email: "Ana@Example.com", origin: "SJO", destination: "Madrid" });
const body = await r.json();
assert.ok(body.ok, JSON.stringify(body));
assert.equal(r.headers.get("Access-Control-Allow-Origin"), env.SITE_URL);
assert.equal(sent[0].body.to[0], "ana@example.com");
const confirmUrl = sent[0].body.html.match(/href="([^"]+)"/)[1];
assert.equal(subs().find((s) => s.channel === "email").status, "pending");

// Confirmar y darse de baja
r = await call(new URL(confirmUrl).pathname + new URL(confirmUrl).search);
assert.equal(r.status, 302);
assert.match(r.headers.get("Location"), /\/\?alerta=confirmada$/);
assert.equal(subs().find((s) => s.channel === "email").status, "active");

// API para el buscador (con clave)
assert.equal((await call("/api/subscriptions")).status, 403);
r = await call("/api/subscriptions", { headers: { Authorization: `Bearer ${await adminToken(env)}` } });
const list = await r.json();
assert.equal(list.length, 2);
const tok = list.find((s) => s.channel === "email").token;
r = await call(`/api/unsubscribe?t=${tok}`);
assert.match(r.headers.get("Location"), /\?alerta=baja$/);
assert.equal(subs().find((s) => s.channel === "email").status, "removed");
assert.match((await call("/api/unsubscribe?t=nope")).headers.get("Location"), /\?alerta=invalido$/);

// Honeypot
sent.length = 0;
r = await post({ email: "bot@x.com", origin: "SJO", destination: "Madrid", website: "spam" });
assert.ok((await r.json()).ok && sent.length === 0);

// Autocompletar
r = await call("/api/places?term=madrid");
assert.equal((await r.json())[0].code, "MAD");

// Reloj: sin token no hace nada; con token pide a GitHub correr el workflow en main
assert.equal(await dispatchSearch({ ...env, GH_REPO: "o/r", GH_WORKFLOW: "run.yml" }), false);
sent.length = 0;
const pending = [];
await worker.scheduled({ cron: "17 * * * *" },
  { ...env, GH_DISPATCH_TOKEN: "ghp_x", GH_REPO: "Mael0rd/buscavuelosbaratos", GH_WORKFLOW: "run.yml" },
  { waitUntil: (p) => pending.push(p) });
await Promise.all(pending);
assert.equal(sent.length, 1);
assert.match(sent[0].url, /api\.github\.com\/repos\/Mael0rd\/buscavuelosbaratos\/actions\/workflows\/run\.yml\/dispatches$/);
assert.deepEqual(sent[0].body, { ref: "main" });

// Almacén privado (token de Threads)
const adm = { Authorization: `Bearer ${await adminToken(env)}`, "Content-Type": "application/json" };
assert.equal((await call("/api/kv/threads_token")).status, 403);
assert.equal((await call("/api/kv/threads_token", { headers: adm })).status, 404);
r = await call("/api/kv/threads_token", { method: "PUT", headers: adm, body: JSON.stringify({ value: "TH1" }) });
assert.ok((await r.json()).ok);
await call("/api/kv/threads_token", { method: "PUT", headers: adm, body: JSON.stringify({ value: "TH2" }) });
assert.equal((await (await call("/api/kv/threads_token", { headers: adm })).json()).value, "TH2");
assert.equal((await call("/api/kv/threads_token", { method: "PUT", headers: { Authorization: "Bearer x" },
  body: JSON.stringify({ value: "hack" }) })).status, 403);

console.log("Worker: todas las pruebas pasaron ✔");
