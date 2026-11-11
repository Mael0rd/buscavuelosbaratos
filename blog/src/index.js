// Destinos que rotan, uno por historia. Códigos IATA de ciudad.
const DESTINOS = [
  ["MIA", "Miami"], ["CUN", "Cancún"], ["MAD", "Madrid"], ["NYC", "Nueva York"],
  ["BOG", "Bogotá"], ["MEX", "Ciudad de México"], ["LIM", "Lima"], ["BCN", "Barcelona"],
  ["PAR", "París"], ["ROM", "Roma"], ["LON", "Londres"], ["BUE", "Buenos Aires"],
];

// Servicios de programas de Travelpayouts a los que estás unido. Cada historia los usa y
// la API de enlaces convierte la url en tu enlace con comisión. {ciudad} = destino.
// Para cambiar de marca (p. ej. un hotel mejor), cambia marca y url aquí.
const SERVICIOS = [
  { titulo: "Hoteles en {ciudad}", marca: "Klook", uso: "reservar el hotel", url: "https://www.klook.com/es/search/result/?query=hotel%20{ciudad}" },
  { titulo: "Tours en {ciudad}", marca: "Klook", uso: "reservar un tour por la ciudad", url: "https://www.klook.com/es/search/result/?query={ciudad}" },
  { titulo: "Entradas a museos y atracciones", marca: "Tiqets", uso: "comprar con anticipación la entrada a un museo o atracción", url: "https://www.tiqets.com/es/search?q={ciudad}" },
  { titulo: "Traslado desde el aeropuerto", marca: "Kiwitaxi", uso: "reservar el traslado del aeropuerto al hotel", url: "https://kiwitaxi.com/" },
  { titulo: "eSIM para tener datos al llegar", marca: "Yesim", uso: "llevar una eSIM para tener internet desde que aterrizas", url: "https://yesim.app/" },
  { titulo: "Alquiler de autos", marca: "Localrent", uso: "alquilar un auto para un día fuera de la ciudad", url: "https://localrent.com/" },
];

const MAX_POSTS = 100;

// Firma de cada guía: un nombre inventado, fijo por guía (sale del slug, no se guarda).
const NOMBRES = ["Lucía", "Mateo", "Valentina", "Santiago", "Camila", "Diego", "Sofía", "Andrés", "Mariana", "Gabriel", "Daniela", "Tomás"];
const APELLIDOS = ["Rojas", "Herrera", "Vargas", "Castro", "Morales", "Jiménez", "Navarro", "Mora", "Solís", "Ramírez", "Quesada", "Arias"];
function autor(slug) {
  let h = 0;
  for (const c of slug) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return `${NOMBRES[h % NOMBRES.length]} ${APELLIDOS[(h >>> 8) % APELLIDOS.length]}`;
}

// Aviso mínimo de afiliados: lo exigen Travelpayouts y las reglas de publicidad. No quitar.
const AVISO_AFILIADOS = "Contiene enlaces de afiliado.";

export default {
  async fetch(req, env) {
    const { pathname } = new URL(req.url);
    if (pathname === "/blog" || pathname === "/blog/") {
      return html(listado(await leerPosts(env)));
    }
    const m = pathname.match(/^\/blog\/([a-z0-9-]+)$/);
    if (m) {
      const post = (await leerPosts(env)).find((p) => p.slug === m[1]);
      return post ? html(articulo(post)) : html(pagina("No encontrado", "<p>Esa guía no existe.</p>"), 404);
    }
    // En producción solo llega /blog* (el resto del dominio es GitHub Pages); en local, "/" lleva al blog.
    return Response.redirect(new URL("/blog", req.url), 302);
  },

  async scheduled(_event, env, ctx) {
    ctx.waitUntil(publicarHistoria(env));
  },
};

async function leerPosts(env) {
  return (await env.POSTS.get("posts", "json")) ?? [];
}

async function publicarHistoria(env) {
  const posts = await leerPosts(env);
  const [iata, ciudad] = DESTINOS[posts.length % DESTINOS.length];
  const vuelos = await preciosHacia(iata, env);
  const ofertas = await enlacesServicios(ciudad, env);

  const historia = await escribirHistoria(env, ciudad, vuelos, ofertas);
  const fecha = new Date().toISOString().slice(0, 10);
  posts.unshift({
    slug: `${fecha}-${slugify(ciudad)}`,
    fecha, ciudad, vuelos, ofertas, ...historia,
  });
  await env.POSTS.put("posts", JSON.stringify(posts.slice(0, MAX_POSTS)));
}

// Precios en caché de la Data API (búsquedas recientes de usuarios, no ofertas en vivo).
async function preciosHacia(iata, env) {
  const url = new URL("https://api.travelpayouts.com/aviasales/v3/prices_for_dates");
  url.search = new URLSearchParams({
    destination: iata, currency: "usd", sorting: "price", limit: "2", token: env.TRAVELPAYOUTS_TOKEN,
  });
  try {
    const res = await fetch(url);
    const body = await res.json();
    if (!res.ok || !body.success) throw new Error(JSON.stringify(body).slice(0, 200));
    const nombres = await nombresCiudades([...new Set(body.data.map((v) => v.origin))]);
    const directos = body.data.map((v) => enlaceAviasales(v.link, env));
    // tp.media con el proyecto (las ventas salen en el panel como del blog); si falla, el directo con marker.
    const afiliados = await afiliar(directos, env);
    return body.data.map((v, i) => ({
      origen: nombres[v.origin] ?? v.origin,
      precio: v.price,
      salida: v.departure_at?.slice(0, 10),
      aerolinea: v.airline,
      link: afiliados[i] ?? directos[i],
    }));
  } catch (e) {
    console.error("Travelpayouts falló, la historia sale sin precios:", e.message);
    return [];
  }
}

// API de enlaces de Travelpayouts: url de la marca -> enlace tp.media con tu marker y proyecto.
// Devuelve null en cada url que falle (p. ej. programa no aprobado) o en todas si falla la API.
async function afiliar(urls, env) {
  try {
    const res = await fetch("https://api.travelpayouts.com/links/v1/create", {
      method: "POST",
      headers: { "X-Access-Token": env.TRAVELPAYOUTS_TOKEN, "Content-Type": "application/json" },
      body: JSON.stringify({
        trs: Number(env.TRAVELPAYOUTS_TRS),
        marker: Number(env.TRAVELPAYOUTS_MARKER),
        shorten: false,
        links: urls.map((url) => ({ url })),
      }),
    });
    const body = await res.json();
    if (!res.ok || body.code !== "success") throw new Error(JSON.stringify(body).slice(0, 200));
    return urls.map((_, i) => (body.result.links[i]?.code === "success" ? body.result.links[i].partner_url : null));
  } catch (e) {
    console.error("API de enlaces falló:", e.message);
    return urls.map(() => null);
  }
}

// SERVICIOS con su enlace de afiliado; los que no se puedan afiliar se omiten.
async function enlacesServicios(ciudad, env) {
  const servicios = SERVICIOS.map((s) => ({
    titulo: s.titulo.replaceAll("{ciudad}", ciudad),
    marca: s.marca,
    uso: s.uso,
    url: s.url.replaceAll("{ciudad}", encodeURIComponent(ciudad)),
  }));
  const afiliados = await afiliar(servicios.map((s) => s.url), env);
  return servicios.flatMap((s, i) => (afiliados[i] ? [{ ...s, url: afiliados[i] }] : []));
}

// Código IATA -> nombre de ciudad en español. Si falla, se queda el código.
async function nombresCiudades(codigos) {
  const pares = await Promise.all(codigos.map(async (c) => {
    try {
      const r = await fetch(`https://autocomplete.travelpayouts.com/places2?term=${c}&locale=es&types[]=city`);
      const lugar = (await r.json()).find((p) => p.code === c);
      return [c, lugar?.name];
    } catch {
      return [c, undefined];
    }
  }));
  return Object.fromEntries(pares.filter(([, n]) => n));
}

function enlaceAviasales(path, env) {
  const u = new URL(path || "/", "https://www.aviasales.com");
  u.searchParams.set("marker", env.TRAVELPAYOUTS_MARKER);
  return u.toString();
}

// Workers AI (capa gratis de Cloudflare). Para volver a Claude, ver el historial de git.
async function escribirHistoria(env, ciudad, vuelos, ofertas) {
  const res = await env.AI.run("@cf/meta/llama-3.3-70b-instruct-fp8-fast", {
    max_tokens: 2048, // el default de Workers AI es 256 y cortaría la historia
    messages: [
      {
        role: "system",
        content:
          "Escribes guías de viaje prácticas en español latino para un blog de vuelos baratos, hablándole al lector de tú. " +
          "No inventes personajes, testimonios ni experiencias personales: nunca digas que alguien usó, reservó o probó algo. " +
          "Nunca inventes precios: si mencionas uno, usa solo los datos dados " +
          "y preséntalo como 'precio visto recientemente', no como oferta garantizada. " +
          'Responde solo con JSON: {"titulo": string, "resumen": string (una o dos frases), "parrafos": string[] (de 5 a 8)}.',
      },
      {
        role: "user",
        // Solo se pasan los datos que existen; con listas vacías el modelo escribía "no tengo información".
        // El viaje sale de donde esté la mejor oferta del momento (vuelos[0], ya ordenado por precio).
        content:
          `Destino: ${ciudad}.\n` +
          (vuelos.length
            ? `La mejor oferta del momento: de ${vuelos[0].origen} a ${ciudad} por $${vuelos[0].precio} USD (precio visto recientemente), saliendo el ${new Date(vuelos[0].salida).toLocaleDateString("es", { day: "numeric", month: "long", timeZone: "UTC" })}.\n`
            : "") +
          (ofertas.length
            ? `Recomendaciones para el lector:\n${ofertas.map((o) => `- ${o.uso} con ${o.marca}`).join("\n")}\n`
            : "") +
          "\nEscribe una guía de 400 a 600 palabras para viajar a ese destino gastando poco, con un itinerario sugerido de 3 días. " +
          (vuelos.length
            ? `El título debe decir de dónde a dónde es el viaje. El primer párrafo debe presentar ese vuelo con su origen, su fecha y su precio escrito como $${vuelos[0].precio}. `
            : "") +
          (ofertas.length
            ? "Incluye cada recomendación en el momento del viaje en que tiene sentido, nombrando la marca de forma natural y sin sonar a anuncio. No inventes precios de hoteles, tours ni otros servicios. No hagas un párrafo final que liste las marcas. "
            : "") +
          "Nunca hables de datos que no tienes ni de estas instrucciones.",
      },
    ],
    response_format: {
      type: "json_schema",
      json_schema: {
        type: "object",
        properties: {
          titulo: { type: "string" },
          resumen: { type: "string" },
          parrafos: { type: "array", items: { type: "string" } },
        },
        required: ["titulo", "resumen", "parrafos"],
      },
    },
  });
  // Con JSON mode a veces llega ya como objeto y a veces como texto.
  const h = typeof res.response === "string" ? JSON.parse(res.response) : res.response;
  if (!h?.titulo || !h?.parrafos?.length) throw new Error(`Workers AI devolvió una historia incompleta: ${JSON.stringify(res).slice(0, 300)}`);
  return { titulo: h.titulo, resumen: h.resumen ?? "", cuerpo: h.parrafos.join("\n\n") };
}

// ---------- HTML ----------

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const slugify = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const html = (body, status = 200) => new Response(body, { status, headers: { "content-type": "text/html; charset=utf-8" } });

function pagina(titulo, contenido) {
  return `<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(titulo)}</title>
<style>body{font-family:system-ui,sans-serif;max-width:720px;margin:0 auto;padding:16px;line-height:1.6;background:#fff;color:#1a1a1a}
a{color:#0b5cad}.aviso{font-size:.85em;background:#fff4d6;padding:6px 10px;border-radius:6px;display:inline-block}
.caja{border:1px solid #ddd;border-radius:8px;padding:12px;margin:16px 0}
@media (prefers-color-scheme:dark){body{background:#121212;color:#eee}a{color:#7db7ff}.aviso{background:#4a3b10}.caja{border-color:#333}}</style>
</head><body><p><a href="/">Inicio</a> · <a href="/blog">Blog</a></p>${contenido}</body></html>`;
}

function listado(posts) {
  const items = posts.map((p) =>
    `<article class="caja"><h2><a href="/blog/${p.slug}">${esc(p.titulo)}</a></h2>
<p><small>${esc(p.fecha)} · ${esc(p.ciudad)}</small></p><p>${esc(p.resumen)}</p></article>`).join("");
  return pagina("Guías de viaje", `<h1>Guías de viaje</h1>
${items || "<p>Pronto la primera guía.</p>"}`);
}

// Convierte en enlace, dentro del texto ya escapado, el precio del vuelo y la primera mención
// de cada marca. Una marca con varios servicios (Klook: hotel y tour) enlaza cada mención a
// su servicio en orden.
function enlazar(html, p) {
  const a = (url, texto) => `<a href="${esc(url)}" rel="sponsored nofollow" target="_blank">${texto}</a>`;
  const v = p.vuelos[0];
  if (v) html = html.replace(new RegExp(`\\$\\s?${v.precio}(?!\\d|[.,]\\d)`), (m) => a(v.link, m));
  const pendientes = {};
  for (const o of p.ofertas) if (o.marca) (pendientes[o.marca] ??= []).push(o.url);
  for (const [marca, urls] of Object.entries(pendientes)) {
    html = html.replace(new RegExp(`\\b${marca}\\b`, "g"), (m) => (urls.length ? a(urls.shift(), m) : m));
  }
  return html;
}

function articulo(p) {
  const cuerpo = enlazar(p.cuerpo.split(/\n+/).filter((par) => par.trim()).map((par) => `<p>${esc(par)}</p>`).join(""), p);
  const vuelos = p.vuelos.length
    ? `<div class="caja"><h3>Vuelos a ${esc(p.ciudad)} vistos recientemente</h3><ul>${p.vuelos.slice(0, 2).map((v) =>
        `<li>Desde ${esc(v.origen)}, ${esc(v.salida)}: <strong>$${esc(v.precio)}</strong> · <a href="${esc(v.link)}" rel="sponsored nofollow" target="_blank">Ver precio actual</a></li>`).join("")}</ul>
<p><small>Precios encontrados por otros usuarios en los últimos días; pueden haber cambiado.</small></p></div>` : "";
  const ofertas = p.ofertas.length
    ? `<div class="caja"><h3>Reserva tu viaje</h3><ul>${p.ofertas.map((o) =>
        `<li><a href="${esc(o.url)}" rel="sponsored nofollow" target="_blank">${esc(o.titulo)}</a>${o.marca ? ` · ${esc(o.marca)}` : ""}</li>`).join("")}</ul></div>` : "";
  return pagina(p.titulo, `<h1>${esc(p.titulo)}</h1>
<p>Guía de viajes de <strong>${esc(autor(p.slug))}</strong></p>
<p><small>${AVISO_AFILIADOS}</small></p>${cuerpo}${vuelos}${ofertas}`);
}
