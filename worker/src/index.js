// Servidor de alertas de buscavuelosbaratos.com (Cloudflare Worker + D1)
//
// POST /telegram            webhook del bot (/alerta, /misalertas, /cancelar, /ayuda)
// GET  /api/places?term=    autocompletar destinos (proxy de Travelpayouts)
// POST /api/subscribe       formulario web: {email, origin, destination, website(honeypot)}
// GET  /api/confirm?t=      confirma una alerta por correo
// GET  /api/unsubscribe?t=  da de baja una alerta
// GET  /api/subscriptions   lista de alertas activas (solo para el buscador, con clave)
import DATA from "./origins.json";

const ORIGINS = DATA.origins;
const COUNTRIES = DATA.countries;
const MAX_ALERTS = 15;

// ---------- utilidades ----------
const enc = new TextEncoder();
async function sha256hex(s) {
  const b = await crypto.subtle.digest("SHA-256", enc.encode(s));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}
export const adminToken = (env) => sha256hex("bvb-admin:" + env.TELEGRAM_BOT_TOKEN);
export const webhookSecret = async (env) =>
  (await sha256hex("bvb-webhook:" + env.TELEGRAM_BOT_TOKEN)).slice(0, 48);

function newToken() {
  const a = new Uint8Array(18);
  crypto.getRandomValues(a);
  return [...a].map((x) => x.toString(16).padStart(2, "0")).join("");
}
export const norm = (s) =>
  (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const json = (o, status = 200, headers = {}) =>
  new Response(JSON.stringify(o), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...headers },
  });
const redirect = (url) => Response.redirect(url, 302);

function cors(req, env) {
  const origin = req.headers.get("Origin") || "";
  const site = env.SITE_URL;
  const allowed = [site, site.replace("https://", "https://www.")];
  return {
    "Access-Control-Allow-Origin": allowed.includes(origin) ? origin : site,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    Vary: "Origin",
  };
}

// ---------- ciudades ----------
export function resolveOrigin(text) {
  const raw = (text || "").trim();
  const up = raw.toUpperCase();
  if (ORIGINS[up]) return { code: up };
  const n = norm(raw);
  if (!n) return null;
  for (const [code, o] of Object.entries(ORIGINS)) if (norm(o.name) === n) return { code };
  const country = COUNTRIES.find((c) => norm(c.name) === n || norm(c.id.replace(/-/g, " ")) === n);
  if (country) {
    return country.origins.length === 1 ? { code: country.origins[0] } : { choices: country.origins };
  }
  const partial = Object.entries(ORIGINS).filter(([, o]) => norm(o.name).startsWith(n));
  if (partial.length === 1) return { code: partial[0][0] };
  if (partial.length > 1) return { choices: partial.map(([c]) => c) };
  return null;
}

export async function places(term) {
  const u = new URL("https://autocomplete.travelpayouts.com/places2");
  u.searchParams.set("term", term);
  u.searchParams.set("locale", "es");
  u.searchParams.append("types[]", "city");
  try {
    const r = await fetch(u, { cf: { cacheTtl: 86400 } });
    if (!r.ok) return [];
    const a = await r.json();
    return a
      .filter((p) => p.code)
      .slice(0, 8)
      .map((p) => ({ code: p.code, name: p.name, country: p.country_name || "", cc: p.country_code || "" }));
  } catch {
    return [];
  }
}

async function resolveDest(text) {
  const t = (text || "").trim();
  if (!t) return null;
  const list = await places(t);
  if (!list.length) return null;
  const exact = list.find((p) => p.code === t.toUpperCase());
  return exact || list[0];
}

// ---------- alertas ----------
async function countActive(env, channel, address) {
  const r = await env.DB.prepare(
    "SELECT COUNT(*) AS n FROM subscriptions WHERE channel=? AND address=? AND status!='removed'"
  ).bind(channel, address).first();
  return r ? r.n : 0;
}

// Crea o reactiva una alerta. Devuelve {status, token} o {error}
async function upsertSub(env, channel, address, originCode, dest) {
  const o = ORIGINS[originCode];
  if (!o) return { error: "origen" };
  if (dest.code === originCode) return { error: "igual" };
  if (dest.cc && dest.cc === o.cc) return { error: "nacional" };
  const prev = await env.DB.prepare(
    "SELECT * FROM subscriptions WHERE channel=? AND address=? AND origin=? AND destination=?"
  ).bind(channel, address, originCode, dest.code).first();
  if (prev && prev.status === "active") return { status: "ya", token: prev.token };
  if (!prev && (await countActive(env, channel, address)) >= MAX_ALERTS) return { error: "limite" };

  const status = channel === "telegram" ? "active" : "pending";
  const token = newToken();
  await env.DB.prepare(
    `INSERT INTO subscriptions (channel, address, origin, origin_name, destination, dest_name, status, token, confirmed_at)
     VALUES (?,?,?,?,?,?,?,?, CASE WHEN ?='active' THEN datetime('now') END)
     ON CONFLICT(channel, address, origin, destination) DO UPDATE SET
       status=excluded.status, token=excluded.token, dest_name=excluded.dest_name,
       created_at=datetime('now'), confirmed_at=excluded.confirmed_at`
  ).bind(channel, address, originCode, o.name, dest.code, dest.name, status, token, status).run();
  return { status, token };
}

// ---------- correo (Resend) ----------
async function sendEmail(env, to, subject, html) {
  const r = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: env.MAIL_FROM, to: [to], subject, html }),
  });
  if (!r.ok) console.log("resend", r.status, await r.text());
  return r.ok;
}

function confirmEmailHtml(env, originName, destName, token) {
  const url = `${env.API_URL}/api/confirm?t=${token}`;
  return `<div style="font-family:system-ui,Arial,sans-serif;max-width:520px;margin:auto;color:#14213d">
  <h2 style="margin:0 0 12px">Confirma tu alerta de vuelos ✈️</h2>
  <p>Te avisaremos cuando encontremos una oferta real para <b>${esc(originName)} → ${esc(destName)}</b>.</p>
  <p style="margin:24px 0"><a href="${url}" style="background:#e85d04;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:bold">Confirmar alerta</a></p>
  <p style="color:#5c6577;font-size:13px">Si no pediste esta alerta, ignora este correo y no recibirás nada.</p>
  <p style="color:#5c6577;font-size:13px">Busca Vuelos Baratos · ${esc(env.SITE_URL.replace("https://", ""))}</p></div>`;
}

async function handleSubscribe(req, env) {
  let body = {};
  try {
    body = await req.json();
  } catch {
    return json({ ok: false, error: "Datos inválidos." }, 400, cors(req, env));
  }
  if (body.website) return json({ ok: true }, 200, cors(req, env)); // honeypot: bots
  const email = String(body.email || "").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email) || email.length > 200)
    return json({ ok: false, error: "Revisa el correo." }, 400, cors(req, env));
  const origin = String(body.origin || "").toUpperCase();
  if (!ORIGINS[origin]) return json({ ok: false, error: "Elige una ciudad de salida." }, 400, cors(req, env));
  const dest = await resolveDest(body.destination);
  if (!dest) return json({ ok: false, error: "No encontramos ese destino." }, 400, cors(req, env));

  const res = await upsertSub(env, "email", email, origin, dest);
  const msgs = {
    nacional: "Solo vigilamos vuelos internacionales: elige un destino en otro país.",
    igual: "El origen y el destino no pueden ser iguales.",
    limite: `Puedes tener hasta ${MAX_ALERTS} alertas por correo.`,
    origen: "Elige una ciudad de salida.",
  };
  if (res.error) return json({ ok: false, error: msgs[res.error] }, 400, cors(req, env));
  if (res.status === "ya")
    return json({ ok: true, message: "Ya tenías esta alerta activa. Te avisaremos cuando haya oferta." }, 200, cors(req, env));

  const ok = await sendEmail(env, email, `Confirma tu alerta: ${ORIGINS[origin].name} → ${dest.name}`,
    confirmEmailHtml(env, ORIGINS[origin].name, dest.name, res.token));
  if (!ok) return json({ ok: false, error: "No pudimos enviar el correo. Intenta más tarde." }, 502, cors(req, env));
  return json({ ok: true, message: `Te enviamos un correo a ${email}. Ábrelo y confirma la alerta ${ORIGINS[origin].name} → ${dest.name}.` },
    200, cors(req, env));
}

// ---------- Telegram ----------
async function tg(env, method, payload) {
  const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) console.log("telegram", method, r.status, await r.text());
  return r;
}
const say = (env, chat_id, text, extra = {}) =>
  tg(env, "sendMessage", { chat_id, text, parse_mode: "HTML", link_preview_options: { is_disabled: true }, ...extra });

async function setState(env, chat, step, origin = null) {
  if (!step) return env.DB.prepare("DELETE FROM bot_state WHERE chat_id=?").bind(chat).run();
  return env.DB.prepare(
    `INSERT INTO bot_state (chat_id, step, origin, updated_at) VALUES (?,?,?,datetime('now'))
     ON CONFLICT(chat_id) DO UPDATE SET step=excluded.step, origin=excluded.origin, updated_at=datetime('now')`
  ).bind(chat, step, origin).run();
}
const getState = (env, chat) =>
  env.DB.prepare("SELECT * FROM bot_state WHERE chat_id=? AND updated_at >= datetime('now','-1 day')")
    .bind(chat).first();

function originsHelp() {
  return COUNTRIES.map((c) => `${c.flag} ${c.name}: ${c.origins.map((o) => ORIGINS[o].name).join(", ")}`).join("\n");
}

const HELP =
  "✈️ <b>Busca Vuelos Baratos</b>\n\n" +
  "Te aviso por aquí cuando encuentre una <b>oferta real</b> para la ruta que elijas.\n\n" +
  "🔔 /alerta — crear una alerta (te pregunto origen y destino)\n" +
  "   También puedes escribir directo: <code>/alerta San José a Madrid</code>\n" +
  "📋 /misalertas — ver y quitar tus alertas\n" +
  "❌ /cancelar — cancelar lo que estás haciendo";

async function askOrigin(env, chat) {
  await setState(env, chat, "origin");
  return say(env, chat,
    "🛫 ¿Desde qué ciudad sales?\nEscribe la ciudad o el país. Ciudades disponibles:\n\n" + esc(originsHelp()));
}

async function askChoice(env, chat, choices) {
  const kb = choices.map((c) => [{ text: `${ORIGINS[c].name} (${c})` }]);
  return say(env, chat, "¿Desde cuál ciudad?", {
    reply_markup: { keyboard: kb, one_time_keyboard: true, resize_keyboard: true },
  });
}

async function createTelegramAlert(env, chat, originCode, destText) {
  const dest = await resolveDest(destText);
  if (!dest) {
    await setState(env, chat, "dest", originCode);
    return say(env, chat, "No encontré ese destino 🤔 Escribe el nombre de la ciudad (por ejemplo <i>Madrid</i> o <i>Miami</i>).");
  }
  const res = await upsertSub(env, "telegram", chat, originCode, dest);
  const msgs = {
    nacional: "Solo vigilamos vuelos internacionales. Escribe un destino en otro país.",
    igual: "El destino no puede ser la misma ciudad de salida. Escribe otro destino.",
    limite: `Ya tienes ${MAX_ALERTS} alertas. Quita alguna con /misalertas.`,
  };
  if (res.error) {
    if (res.error === "limite") await setState(env, chat, null);
    else await setState(env, chat, "dest", originCode);
    return say(env, chat, msgs[res.error] || "No pude crear la alerta.");
  }
  await setState(env, chat, null);
  const route = `<b>${esc(ORIGINS[originCode].name)} → ${esc(dest.name)}</b>${dest.country ? ", " + esc(dest.country) : ""}`;
  return say(env, chat,
    (res.status === "ya" ? "Ya tenías esta alerta activa ✅\n" : "✅ Alerta creada\n") +
    `${route}\n\nTe escribo aquí cuando el precio sea una oferta real. Para ver o quitar tus alertas: /misalertas`,
    { reply_markup: { remove_keyboard: true } });
}

async function listAlerts(env, chat) {
  const { results } = await env.DB.prepare(
    "SELECT id, origin_name, dest_name FROM subscriptions WHERE channel='telegram' AND address=? AND status='active' ORDER BY id"
  ).bind(chat).all();
  if (!results.length) return say(env, chat, "No tienes alertas activas. Crea una con /alerta");
  const text = "📋 <b>Tus alertas</b>\n\n" +
    results.map((r, i) => `${i + 1}. ${esc(r.origin_name)} → ${esc(r.dest_name)}`).join("\n") +
    "\n\nToca una para quitarla:";
  const kb = results.map((r, i) => [{ text: `❌ Quitar ${i + 1}. ${r.origin_name} → ${r.dest_name}`, callback_data: `del:${r.id}` }]);
  return say(env, chat, text, { reply_markup: { inline_keyboard: kb } });
}

function parseRoute(args) {
  const parts = args.split(/\s+(?:a|hacia|->|→|>|-)\s+|\s*(?:->|→|>|,)\s*/i).filter(Boolean);
  if (parts.length === 2) return parts;
  const toks = args.trim().split(/\s+/);
  if (toks.length === 2) return toks; // p. ej. "SJO MAD"
  return null;
}

async function handleText(env, chat, text) {
  const [cmdRaw, ...rest] = text.trim().split(/\s+/);
  const cmd = cmdRaw.toLowerCase().split("@")[0];
  const args = rest.join(" ");

  if (cmd === "/start" || cmd === "/ayuda" || cmd === "/help") {
    await setState(env, chat, null);
    return say(env, chat, HELP);
  }
  if (cmd === "/cancelar") {
    await setState(env, chat, null);
    return say(env, chat, "Listo, cancelado.", { reply_markup: { remove_keyboard: true } });
  }
  if (cmd === "/misalertas") return listAlerts(env, chat);
  if (cmd === "/alerta") {
    if (!args) return askOrigin(env, chat);
    const route = parseRoute(args);
    if (route) {
      const o = resolveOrigin(route[0]);
      if (o && o.code) return createTelegramAlert(env, chat, o.code, route[1]);
    }
    const o = resolveOrigin(args);
    if (o && o.code) {
      await setState(env, chat, "dest", o.code);
      return say(env, chat, `🛫 Saliendo de <b>${esc(ORIGINS[o.code].name)}</b>.\n🛬 ¿A qué ciudad quieres ir?`);
    }
    return askOrigin(env, chat);
  }

  const st = await getState(env, chat);
  if (st && st.step === "origin") {
    const picked = text.match(/\(([A-Z]{3})\)\s*$/); // respuesta del teclado: "Cancún (CUN)"
    const o = resolveOrigin(picked ? picked[1] : text);
    if (!o) return say(env, chat, "No tengo esa ciudad de salida. Escribe una de la lista, o /cancelar.");
    if (o.choices) return askChoice(env, chat, o.choices);
    await setState(env, chat, "dest", o.code);
    return say(env, chat, `🛫 Saliendo de <b>${esc(ORIGINS[o.code].name)}</b>.\n🛬 ¿A qué ciudad quieres ir?`,
      { reply_markup: { remove_keyboard: true } });
  }
  if (st && st.step === "dest") return createTelegramAlert(env, chat, st.origin, text);
  return say(env, chat, HELP);
}

async function handleCallback(env, cq) {
  const chat = String(cq.message?.chat?.id || "");
  const m = /^del:(\d+)$/.exec(cq.data || "");
  if (m) {
    await env.DB.prepare(
      "UPDATE subscriptions SET status='removed' WHERE id=? AND channel='telegram' AND address=?"
    ).bind(Number(m[1]), chat).run();
    await tg(env, "answerCallbackQuery", { callback_query_id: cq.id, text: "Alerta quitada" });
    await tg(env, "deleteMessage", { chat_id: chat, message_id: cq.message.message_id });
    return listAlerts(env, chat);
  }
  return tg(env, "answerCallbackQuery", { callback_query_id: cq.id });
}

async function handleTelegram(req, env) {
  if (req.headers.get("X-Telegram-Bot-Api-Secret-Token") !== (await webhookSecret(env)))
    return new Response("forbidden", { status: 403 });
  const update = await req.json();
  try {
    if (update.callback_query) await handleCallback(env, update.callback_query);
    const msg = update.message;
    if (msg && msg.text && msg.chat && msg.chat.type === "private")
      await handleText(env, String(msg.chat.id), msg.text);
  } catch (e) {
    console.log("error bot", e && e.stack);
  }
  return new Response("ok"); // siempre 200 para que Telegram no reintente
}

// ---------- router ----------
export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const p = url.pathname;
    if (req.method === "OPTIONS") return new Response(null, { headers: cors(req, env) });

    if (p === "/telegram" && req.method === "POST") return handleTelegram(req, env);

    if (p === "/api/places") {
      const term = (url.searchParams.get("term") || "").slice(0, 60);
      return json(term.length >= 2 ? await places(term) : [], 200, cors(req, env));
    }
    if (p === "/api/subscribe" && req.method === "POST") return handleSubscribe(req, env);

    if (p === "/api/confirm" || p === "/api/unsubscribe") {
      const t = url.searchParams.get("t") || "";
      const confirm = p === "/api/confirm";
      const r = await env.DB.prepare(
        confirm
          ? "UPDATE subscriptions SET status='active', confirmed_at=datetime('now') WHERE token=? AND status!='removed'"
          : "UPDATE subscriptions SET status='removed' WHERE token=?"
      ).bind(t).run();
      const ok = r.meta && r.meta.changes > 0;
      return redirect(`${env.SITE_URL}/alertas.html?estado=${ok ? (confirm ? "confirmada" : "baja") : "invalido"}`);
    }

    if (p === "/api/subscriptions") {
      if (req.headers.get("Authorization") !== `Bearer ${await adminToken(env)}`)
        return json({ error: "forbidden" }, 403);
      const { results } = await env.DB.prepare(
        "SELECT id, channel, address, origin, destination, dest_name, token FROM subscriptions WHERE status='active'"
      ).all();
      return json(results);
    }

    if (p === "/") return json({ ok: true, service: "alertas buscavuelosbaratos" });
    return json({ error: "not found" }, 404);
  },
};
