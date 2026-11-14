// Blog estático: las historias viven en historias.js y se publican con deploy.
import HISTORIAS from "./historias.js";

// Aviso mínimo de afiliados: lo exigen Travelpayouts y las reglas de publicidad. No quitar.
const AVISO_AFILIADOS = "Contiene enlaces de afiliado.";

export default {
  async fetch(req) {
    const { pathname, searchParams } = new URL(req.url);
    if (pathname === "/blog" || pathname === "/blog/") {
      const n = Math.max(1, parseInt(searchParams.get("pagina"), 10) || 1);
      return html(listado(HISTORIAS, searchParams.get("region"), n));
    }
    const post = HISTORIAS.find((p) => pathname === `/blog/${p.slug}`);
    if (post) return html(articulo(post, HISTORIAS));
    // Todo lo demás va a la portada del blog: las guías viejas que escribía la IA (ya no existen)
    // y, en local, "/". 301 para que Google pase esas direcciones al blog. En producción solo llega /blog*.
    return Response.redirect(new URL("/blog", req.url), 301);
  },
};

// ---------- HTML ----------

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const slugify = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const html = (body, status = 200) => new Response(body, { status, headers: { "content-type": "text/html; charset=utf-8" } });

// Diseño inspirado en blogs de viaje tipo revista: nota líder + lista, bloques por sección
// con "Ver más", tarjetas con etiqueta, título, resumen y fecha, y "Cargar más" al final.
const SITIO = "Buscavuelosbaratos";
// Buscador de vuelos: el sitio principal (GitHub Pages). En local y en test "/" no lo tiene, por eso va completo.
const BUSCADOR = "https://buscavuelosbaratos.com/";
const POR_PAGINA = 12;
const REGIONES = [...new Set(HISTORIAS.map((p) => p.region))];
const fechaLarga = (f) => new Date(f).toLocaleDateString("es", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const minutos = (p) => Math.max(1, Math.round(p.cuerpo.split(/\s+/).length / 200));
const enlaceRegion = (r) => `/blog?region=${slugify(r)}`;

const ESTILOS = `
:root{--fondo:#faf8f5;--superficie:#fff;--texto:#1d1d1f;--suave:#5f6368;--borde:#e6e2dc;--acento:#c93c10;--acento-txt:#fff;--oscuro:#14213d;--aviso:#fff1d6}
@media (prefers-color-scheme:dark){:root{--fondo:#111418;--superficie:#1b1f24;--texto:#ececec;--suave:#a3a9b0;--borde:#2c3238;--acento:#ff7a50;--acento-txt:#1a0d06;--oscuro:#0b1220;--aviso:#3d3110}}
*{box-sizing:border-box}
body{margin:0;font:17px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--fondo);color:var(--texto)}
h1,h2,h3,.logo{font-family:Montserrat,system-ui,sans-serif;line-height:1.25}
a{color:inherit}
.envoltura{max-width:1160px;margin:0 auto;padding:0 16px}
.franja{background:var(--oscuro);color:#fff;font-size:.85rem;text-align:center;padding:8px 16px}
.franja a{color:#ffb199;font-weight:700}
.cabecera{background:var(--superficie);border-bottom:1px solid var(--borde);position:sticky;top:0;z-index:5}
.cab{display:flex;align-items:center;justify-content:space-between;gap:8px 16px;padding-top:12px;padding-bottom:12px;flex-wrap:wrap}
.logo{text-decoration:none;font-weight:800;font-size:1.35rem;display:flex;flex-direction:column;line-height:1.1}
.logo b{color:var(--acento)}
.logo small{font-family:system-ui,sans-serif;font-weight:600;font-size:.7rem;letter-spacing:.14em;text-transform:uppercase;color:var(--suave)}
.cab nav{display:flex;gap:2px;align-items:center;overflow-x:auto;max-width:100%}
.cab nav a{text-decoration:none;font-weight:600;font-size:.92rem;padding:8px 12px;border-radius:999px;white-space:nowrap}
.cab nav a:hover{background:var(--fondo)}
.boton{display:inline-block;background:var(--acento);color:var(--acento-txt)!important;text-decoration:none;font-weight:700;padding:10px 20px;border-radius:999px}
.cab nav a.boton:hover{background:var(--acento);filter:brightness(1.1)}
main.envoltura{padding-top:32px;padding-bottom:48px}
.destacado{display:grid;grid-template-columns:1.45fr 1fr;gap:24px}
.lista{display:flex;flex-direction:column;gap:16px}
.tarjeta{background:var(--superficie);border-radius:14px;overflow:hidden;border:1px solid var(--borde);display:flex;flex-direction:column;transition:box-shadow .2s,transform .2s}
.tarjeta:hover{box-shadow:0 10px 30px rgba(20,33,61,.12);transform:translateY(-2px)}
.tarjeta-img{position:relative;display:block;text-decoration:none}
.portada{aspect-ratio:16/9;display:flex;align-items:flex-end;padding:16px;color:#fff;position:relative;overflow:hidden;
  background:linear-gradient(135deg,hsl(var(--t) 62% 50%),hsl(calc(var(--t) + 45) 70% 26%))}
.portada::after{content:"✈";position:absolute;right:-.05em;top:-.3em;font-size:9rem;opacity:.16;transform:rotate(-18deg)}
.portada span{font-family:Montserrat,system-ui,sans-serif;font-weight:800;font-size:1.5rem;text-shadow:0 2px 12px rgba(0,0,0,.3);position:relative;z-index:2}
.portada img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transition:transform .5s}
.con-foto::after{content:"";inset:0;opacity:1;transform:none;z-index:1;background:linear-gradient(to top,rgba(0,0,0,.6),rgba(0,0,0,0) 55%)}
.tarjeta:hover .portada img{transform:scale(1.04)}
.grande .portada{aspect-ratio:3/2}.grande .portada span{font-size:2.6rem}
.grande h3{font-size:1.65rem}
.tarjeta-txt{padding:16px 18px 18px;display:flex;flex-direction:column;gap:6px;flex:1}
.etiqueta{font-size:.72rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--acento);text-decoration:none}
.tarjeta h3{margin:0;font-size:1.12rem}
.tarjeta h3 a{text-decoration:none}.tarjeta h3 a:hover{text-decoration:underline}
.resumen{margin:0;color:var(--suave);font-size:.95rem}
.meta{margin:auto 0 0;font-size:.82rem;color:var(--suave)}
.fila{flex-direction:row}.fila .tarjeta-img{flex:0 0 38%}
.fila .portada{height:100%;aspect-ratio:auto;min-height:112px;padding:10px}
.fila .portada span{font-size:1rem}.fila .portada::after{font-size:5rem}
.fila .tarjeta-txt{padding:12px 14px}.fila h3{font-size:1rem}
.bloque{margin-top:56px}
.bloque-cab{display:flex;justify-content:space-between;align-items:baseline;gap:12px;border-bottom:3px solid var(--texto);margin-bottom:22px;padding-bottom:8px}
.bloque-cab h2{margin:0;font-size:1.5rem}
.bloque-cab a{font-weight:700;color:var(--acento);text-decoration:none;font-size:.9rem;white-space:nowrap}
.rejilla{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(280px,100%),1fr));gap:24px}
.centro{text-align:center;margin-top:48px}
.titulo-seccion{font-size:2rem;margin:0 0 24px}
.art-cab{max-width:780px;margin:0 auto 28px;text-align:center}
.art-cab h1{font-size:clamp(1.8rem,4vw,2.7rem);margin:8px 0 12px}
.entradilla{font-size:1.15rem;color:var(--suave);margin:0 0 14px}
.portada.ancha{aspect-ratio:21/8;border-radius:18px;padding:28px}.portada.ancha span{font-size:clamp(2rem,6vw,3.6rem)}.portada.ancha::after{font-size:16rem}
.texto{max-width:720px;margin:36px auto 0;font-size:1.1rem;line-height:1.75}
.texto h2{font-size:1.4rem;margin:2em 0 .4em}
.texto>p:first-child::first-letter{float:left;font-family:Montserrat,system-ui,sans-serif;font-weight:800;font-size:3.6em;line-height:.85;margin:.06em .1em 0 0;color:var(--acento)}
.texto figure{margin:2em 0}
.texto figure img{display:block;width:100%;aspect-ratio:3/2;object-fit:cover;border-radius:14px;background:var(--borde)}
.texto figcaption{font-size:.85rem;color:var(--suave);margin-top:8px}
.texto blockquote{margin:1.8em 0;padding:4px 0 4px 20px;border-left:4px solid var(--acento);font-family:Montserrat,system-ui,sans-serif;font-weight:700;font-size:1.3rem;line-height:1.45}
.consejos{max-width:720px;margin:48px auto 0;padding-top:28px;border-top:3px solid var(--texto)}
.consejos h2{font-size:1.5rem;margin:0 0 6px}
.aviso{font-size:.82rem;background:var(--aviso);padding:6px 12px;border-radius:8px;display:inline-block;margin:0 0 18px}
.consejos ul{list-style:none;margin:0;padding:0;display:grid;gap:14px}
.consejo{background:var(--superficie);border:1px solid var(--borde);border-radius:14px;padding:18px;display:flex;gap:16px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.consejo div{flex:1 1 280px}
.consejo h3{margin:0 0 4px;font-size:1.05rem}
.consejo p{margin:0;color:var(--suave);font-size:.95rem}
.consejo .boton{padding:9px 18px;font-size:.92rem;white-space:nowrap}
.pie{background:var(--oscuro);color:#d7dbe2;padding:40px 0}
.pie .logo{color:#fff}.pie .logo small{color:#9aa3b2}.pie .logo b{color:#ff8a63}
.pie nav{display:flex;flex-wrap:wrap;gap:8px 20px;margin:18px 0}.pie nav a{text-decoration:none;color:#fff;font-weight:600}
.legal{font-size:.82rem;color:#9aa3b2;margin:4px 0}
.vacio{text-align:center;padding:80px 16px}
a:focus-visible{outline:3px solid var(--acento);outline-offset:2px}
@media (max-width:900px){.destacado{grid-template-columns:1fr}}
@media (max-width:520px){.fila .tarjeta-img{flex-basis:34%}.grande .portada span{font-size:1.8rem}.grande h3{font-size:1.3rem}}
@media (prefers-reduced-motion:reduce){.tarjeta,.portada img{transition:none}.tarjeta:hover,.tarjeta:hover .portada img{transform:none}}`;

const LOGO = `<a class="logo" href="/blog"><span>Buscavuelos<b>baratos</b></span><small>Guías de viaje</small></a>`;
const MENU = `<a href="/blog">Inicio</a><a href="/blog?region=todas">Todas las guías</a>${REGIONES.map((r) => `<a href="${enlaceRegion(r)}">${esc(r)}</a>`).join("")}`;

function pagina(titulo, contenido, descripcion = "Guías de viaje para viajar gastando poco.") {
  return `<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(titulo)}</title>
<meta name="description" content="${esc(descripcion)}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&display=swap" rel="stylesheet">
<style>${ESTILOS}</style></head><body>
<div class="franja">✈ Guías nuevas cada mes para viajar gastando poco · <a href="${BUSCADOR}">Buscar vuelos</a></div>
<header class="cabecera"><div class="envoltura cab">${LOGO}<nav aria-label="Secciones">${MENU}<a class="boton" href="${BUSCADOR}">Buscar vuelos</a></nav></div></header>
${contenido}
<footer class="pie"><div class="envoltura">${LOGO}<nav aria-label="Pie">${MENU}</nav>
<p class="legal">${AVISO_AFILIADOS}</p>
<p class="legal">© ${new Date().getUTCFullYear()} buscavuelosbaratos.com</p></div></footer>
</body></html>`;
}

// foto: id de Unsplash (se piden varios tamaños) o url completa.
function imagen(foto, alt, sizes, ya = false) {
  const carga = ya ? 'fetchpriority="high"' : 'loading="lazy"';
  if (foto.startsWith("http")) return `<img src="${esc(foto)}" alt="${esc(alt)}" ${carga}>`;
  const src = (w) => `https://images.unsplash.com/photo-${esc(foto)}?auto=format&fit=crop&w=${w}&q=70`;
  return `<img src="${src(960)}" srcset="${src(480)} 480w, ${src(960)} 960w, ${src(1600)} 1600w" sizes="${sizes}" alt="${esc(alt)}" ${carga}>`;
}

// Bloques del cuerpo: "## " subtítulo, "> " frase destacada, "![pie de foto](foto)" foto, lo demás párrafo.
function bloqueTexto(l) {
  if (l.startsWith("## ")) return `<h2>${esc(l.slice(3))}</h2>`;
  if (l.startsWith("> ")) return `<blockquote>${esc(l.slice(2))}</blockquote>`;
  const f = l.match(/^!\[(.*)\]\((\S+)\)$/);
  if (f) {
    const credito = f[2].startsWith("http") ? "" : " · Foto: Unsplash";
    return `<figure>${imagen(f[2], f[1], "(max-width:760px) 100vw, 720px")}<figcaption>${esc(f[1])}${credito}</figcaption></figure>`;
  }
  return `<p>${esc(l)}</p>`;
}

// Sin foto de portada: degradado de color fijo por ciudad.
function portada(p, clase = "") {
  let h = 0;
  for (const c of p.ciudad) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const arriba = clase === "ancha"; // la del artículo se ve al abrir: se carga ya, el resto en diferido
  const foto = p.foto ? imagen(p.foto, "", arriba ? "100vw" : "(max-width:900px) 100vw, 600px", arriba) : "";
  return `<div class="portada ${clase}${foto ? " con-foto" : ""}" style="--t:${h % 360}" aria-hidden="true">${foto}<span>${esc(p.ciudad)}</span></div>`;
}

function tarjeta(p, variante = "") {
  return `<article class="tarjeta ${variante}">
<a class="tarjeta-img" href="/blog/${p.slug}" tabindex="-1" aria-hidden="true">${portada(p)}</a>
<div class="tarjeta-txt"><a class="etiqueta" href="${enlaceRegion(p.region)}">${esc(p.region)}</a>
<h3><a href="/blog/${p.slug}">${esc(p.titulo)}</a></h3>
${variante !== "fila" && p.resumen ? `<p class="resumen">${esc(p.resumen)}</p>` : ""}
<p class="meta">${fechaLarga(p.fecha)} · ${minutos(p)} min</p></div></article>`;
}

function bloque(titulo, posts, verMas) {
  if (!posts.length) return "";
  return `<section class="bloque"><div class="bloque-cab"><h2>${esc(titulo)}</h2>${verMas ? `<a href="${verMas}">Ver más →</a>` : ""}</div>
<div class="rejilla">${posts.map((p) => tarjeta(p)).join("")}</div></section>`;
}

// /blog: portada. /blog?region=europa o ?pagina=2: rejilla paginada (region=todas = todas).
function listado(posts, regionSlug, n) {
  if (!regionSlug && n === 1) return pagina(`Guías de viaje · ${SITIO}`, portadaBlog(posts));
  const r = REGIONES.find((x) => slugify(x) === regionSlug);
  const lista = r ? posts.filter((p) => p.region === r) : posts;
  const titulo = r ?? "Todas las guías";
  const items = lista.slice((n - 1) * POR_PAGINA, n * POR_PAGINA);
  const mas = lista.length > n * POR_PAGINA
    ? `<p class="centro"><a class="boton" href="/blog?region=${r ? slugify(r) : "todas"}&pagina=${n + 1}">Cargar más</a></p>` : "";
  return pagina(`${titulo} · ${SITIO}`, `<main class="envoltura"><h1 class="titulo-seccion">${esc(titulo)}</h1>
<div class="rejilla">${items.map((p) => tarjeta(p)).join("") || "<p>Aún no hay guías aquí.</p>"}</div>${mas}</main>`);
}

function portadaBlog(posts) {
  if (!posts.length) return `<main class="envoltura vacio"><h1>Guías de viaje</h1><p>Pronto la primera guía.</p></main>`;
  const [lider, ...resto] = posts;
  return `<main class="envoltura">
<section class="destacado" aria-label="Lo más reciente">${tarjeta(lider, "grande")}<div class="lista">${resto.slice(0, 4).map((p) => tarjeta(p, "fila")).join("")}</div></section>
${REGIONES.map((r) => bloque(r, posts.filter((p) => p.region === r).slice(0, 3), enlaceRegion(r))).join("")}
${posts.length > 5 ? `<p class="centro"><a class="boton" href="/blog?region=todas">Ver todas las guías</a></p>` : ""}
</main>`;
}

function articulo(p, posts) {
  const cuerpo = p.cuerpo.split("\n").map((l) => l.trim()).filter(Boolean).map(bloqueTexto).join("");
  const consejos = p.consejos?.length
    ? `<section class="consejos"><h2>Consejos para tu viaje</h2><p class="aviso">${AVISO_AFILIADOS}</p><ul>${p.consejos.map((c) =>
        `<li class="consejo"><div><h3>${esc(c.titulo)}</h3>${c.texto ? `<p>${esc(c.texto)}</p>` : ""}</div>
<a class="boton" href="${esc(c.enlace)}" rel="sponsored nofollow" target="_blank">${c.marca ? `Ver en ${esc(c.marca)}` : "Ver"}</a></li>`).join("")}</ul></section>` : "";
  // Primero las de la misma región, luego las más nuevas.
  const relacionadas = posts.filter((x) => x.slug !== p.slug).sort((a, b) => (b.region === p.region) - (a.region === p.region)).slice(0, 3);
  return pagina(`${p.titulo} · ${SITIO}`, `<main class="envoltura"><article>
<header class="art-cab"><a class="etiqueta" href="${enlaceRegion(p.region)}">${esc(p.region)}</a><h1>${esc(p.titulo)}</h1>
${p.resumen ? `<p class="entradilla">${esc(p.resumen)}</p>` : ""}
<p class="meta">${p.autor ? `Por <strong>${esc(p.autor)}</strong> · ` : ""}${fechaLarga(p.fecha)} · ${minutos(p)} min de lectura</p></header>
${portada(p, "ancha")}
<div class="texto">${cuerpo}</div>${consejos}
</article>${bloque("Sigue leyendo", relacionadas, "/blog")}</main>`, p.resumen || undefined);
}
