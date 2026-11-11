# buscavuelosbaratos.com

Plataforma automática de ofertas de vuelos para Hispanoamérica. Cada hora revisa los precios desde
**19 países (33 ciudades de salida)** hacia cualquier destino internacional, detecta las ofertas
reales comparando contra el historial de cada ruta, verifica que el precio sea reciente y publica en
la web y en Telegram. Las personas pueden crear **alertas por ruta** (correo o bot de Telegram).
Los ingresos vienen de comisiones de afiliado de Travelpayouts (Aviasales).

Todo corre gratis: GitHub Actions (repositorio público), GitHub Pages y el plan gratuito de
Cloudflare Workers.

```
                    ┌──────────── cada hora (GitHub Actions) ────────────┐
Travelpayouts API → │ precios → reglas de oferta → ¿precio reciente? → textos │
                    └──────┬─────────────────┬──────────────────┬────────┘
                           ▼                 ▼                  ▼
                 web estática (Pages)   Telegram (general    avisos de alertas
                 por país + ofertas      + por país)          (Telegram / correo)
                                                                    ▲
         Cloudflare Worker (api.buscavuelosbaratos.com): bot /alerta, formulario,
         confirmación por correo (Resend), bajas — guarda las alertas en D1
```

## Qué publica

Una tarifa se publica solo si cumple **todo** esto:

| Regla | Valor | Dónde se cambia |
|---|---|---|
| Viaje internacional (origen y destino en países distintos) | siempre | — |
| Ida y vuelta, directo o con 1 escala | máx. 1 escala | `search.max_transfers` |
| Duración del viaje | mínimo 3 días entre ida y vuelta | `search.min_trip_days` |
| Precio bajo lo normal (con ≥ 7 días de historial de la ruta) | ≥ 10% bajo la mediana | `deals.drop_pct`, `deals.min_days` |
| Precio bajo lo normal (rutas sin historial aún) | bajo el tope por distancia (p. ej. SJO-MIA ≈ $262, SJO-MAD ≈ $717) **y**, si hay precios de ≥ 3 meses, 10% bajo los otros meses. Es solo la primera criba: el juez final es Google | `deals.cold_start` |
| Candidata en caché (mismo viaje visto en Travelpayouts) | < 7 días | `freshness.max_age_hours` |
| No repetida | misma ruta no antes de 7 días, salvo que baje otro 10% | `deals.repost_*` |

### Precios honestos y ofertas terminadas
La API de datos devuelve precios vistos por usuarios de Aviasales en las últimas 48 h, sin decir
cuándo. Por eso, antes de publicar se consulta `/v2/prices/latest` de la ruta, que sí trae `found_at`,
y se busca el mismo viaje (mismas fechas). En la web y en Telegram se muestra **"Precio visto hace X"**.

Cada corrida revisa las ofertas publicadas. Una oferta **termina** si el precio subió, si no se
reconfirma en 8 días (`freshness.stale_hours`) y no fue verificada en vivo hace poco o si la salida está a menos de 2 días. Al terminar:
sale de las listas, su página muestra "❌ Esta oferta terminó" (sin botón de reservar) y el bot
**edita el post de Telegram** para indicarlo.

### Verificación en vivo antes de Telegram (`bvb/verify.py`)
Travelpayouts (caché, gratis) es el *mapa* que encuentra candidatas; Google Flights es la *lupa*
que confirma la mejor justo antes de publicarla en Telegram:
- Se busca el mismo viaje (mismas fechas, máx. 1 escala). **Google es la referencia:** si marca el
  precio en vivo como **"bajo"** para esa ruta y fechas, se publica. Si dice "típico"/"alto", no.
  Si no da nivel (rutas poco buscadas), el precio en vivo no puede subir más de 15%
  (`verify.price_tolerance`). Si subió y no es "bajo", la oferta termina en todos lados.
  Siempre se muestra el **precio real verificado** de Google.
- **Una verificación por oferta**, no por canal: la oferta verificada va a su canal de país y al
  general. Sirve durante 3 h (`verify.cache_hours`). Tener 2 o 19 canales no cambia el gasto.
- Proveedores en cadena, cada uno con su cuenta gratuita: **SerpApi** (250/mes, `SERPAPI_KEY`) →
  **Apify** (~1.000/mes con $5 de crédito, `APIFY_TOKEN`).
- **La web solo muestra ofertas verificadas en vivo.** Cada corrida re-verifica primero las que se
  verificaron hace más de 12 h (`verify.web_reverify_hours`) y luego las candidatas nuevas; una
  oferta que no se reconfirma en 24 h (`verify.web_max_age_hours`) deja de mostrarse, y si el precio
  subió termina (y su post de Telegram se edita).
- Presupuesto automático: (lo que queda del mes) ÷ (días que faltan), repartido en las 17 h en que
  se publica. **Sin presupuesto no se publica** en Telegram ni aparece en la web nada sin verificar.
  Las alertas no gastan verificaciones (muestran "Precio visto hace X").

## La web
- **Portada** con una sección por país. El país del visitante (detectado por la zona horaria o el
  idioma del navegador, sin servicios externos) aparece primero con "📍 Tu país".
- **`/pais/<país>.html`**: todas las ofertas de ese país + botón para unirse a su canal de Telegram.
- **`/vuelos/<origen>-a-<destino>-<cod>-<cod>.html`** (SEO): página **permanente** por ruta con precio
  típico, el más bajo visto, precio por mes de salida, historial (gráfico), aerolíneas, vuelos directos,
  la oferta verificada vigente y preguntas frecuentes con datos estructurados (FAQPage, BreadcrumbList).
  Se crea cuando la ruta tiene ≥ 3 días de historial (`seo.route_min_days`) y se enlaza desde el país
  y desde cada oferta. Las URL de ofertas viejas redirigen (301) a su ruta vía `_redirects`.
- **`/oferta/<slug>.html`**: detalle, botón de reserva (enlace de afiliado) y "Avísame de esta ruta".
- **`/alertas.html`**: formulario de alertas por correo y acceso al bot.
- Al confirmar o darse de baja de una alerta se llega a la portada con una ventana emergente.
- Banderas como imágenes (Windows no muestra emojis de banderas) y control de caché del CSS.
- Incluye el script de **Travelpayouts Drive** (`templates/base.html`). Su función de abrir ofertas
  al hacer clic en zonas vacías (p. ej. Klook) se desactiva en Travelpayouts → Drive → Advanced settings.

## Telegram
| Canal | Variable de GitHub | Cupo |
|---|---|---|
| General (las mejores de toda la región) | `TELEGRAM_CHANNEL` | 1 por hora, máx. 10 al día |
| Por país (solo ofertas que salen de ese país) | `TELEGRAM_CHANNEL_<PAÍS>`, p. ej. `TELEGRAM_CHANNEL_MEXICO`, `TELEGRAM_CHANNEL_COSTA_RICA` | 2 por hora, máx. 10 al día |

- No se publica de 23:00 a 6:00 (hora local del canal) — `social.quiet_hours`.
- Posts con botones: *Ver precio actual y reservar*, *Compartir en WhatsApp*, *Más ofertas desde el país*.
- Para un canal nuevo: créalo **público**, agrega el bot como administrador (publicar y editar
  mensajes) y crea la variable con el `@usuario` del canal. No hay que tocar el código.
- Workflow **Publicar ejemplo en Telegram**: publica en el canal general la mejor oferta activa del
  país que elijas.

## Alertas por ruta
- **Correo:** formulario en `/alertas.html` → correo de confirmación (doble opt-in) → avisos con
  enlace de baja (`List-Unsubscribe`).
- **Telegram:** `/alerta` (pregunta origen y destino; también `/alerta San José a Madrid`),
  `/misalertas` (lista con botón para quitar), `/cancelar`, `/ayuda`.
- Se avisa solo si la ruta pasa las reglas de oferta y el precio es reciente; no se repite en 7 días
  salvo que baje otro 10% (`alerts.*`). Máximo 15 alertas por persona.
- Servidor: `worker/` (Cloudflare Worker + D1 en `api.buscavuelosbaratos.com`). La clave entre el
  buscador y el Worker se deriva del token del bot, así que no hay que configurarla.

## Puesta en marcha

**Secrets** (*Settings → Secrets and variables → Actions → Secrets*):

| Nombre | Para qué | De dónde sale |
|---|---|---|
| `TRAVELPAYOUTS_TOKEN` | precios | Travelpayouts → Perfil → API token (unirse al programa Aviasales) |
| `TRAVELPAYOUTS_MARKER` | comisión en los enlaces | tu ID de afiliado (marker) |
| `TELEGRAM_BOT_TOKEN` | canal, bot y alertas | @BotFather |
| `RESEND_API_KEY` | correos de alertas | Resend, con el dominio verificado |
| `CLOUDFLARE_API_TOKEN` | desplegar el servidor de alertas | plantilla "Edit Cloudflare Workers" + permiso **D1 Write**, zona del dominio |
| `CLOUDFLARE_ACCOUNT_ID` | ídem | Cloudflare (columna derecha del dominio o en la URL del panel) |
| `GH_DISPATCH_TOKEN` | reloj de Cloudflare: lanzar la búsqueda cada hora | GitHub → token *fine-grained*, solo este repositorio, permiso **Actions: Read and write** |
| `SERPAPI_KEY` | verificación en vivo (Google Flights), 1.er proveedor | serpapi.com → API key (plan gratis) |
| `APIFY_TOKEN` | verificación en vivo, 2.º proveedor | console.apify.com → Settings → API & Integrations |
| `ANTHROPIC_API_KEY` | (opcional) textos redactados por Claude | console.anthropic.com |

**Variables:** `TELEGRAM_CHANNEL` y, por país, `TELEGRAM_CHANNEL_<PAÍS>`.

**Hosting y dominio:**
1. *Settings → Pages → Source: GitHub Actions*; dominio `buscavuelosbaratos.com`; *Enforce HTTPS*.
2. DNS en Cloudflare con **nube gris (DNS only)**: registros A `@` → 185.199.108.153, .109.153,
   .110.153, .111.153 y CNAME `www` → `mael0rd.github.io`.
3. *Actions → Desplegar alertas → Run workflow* (crea la base D1, `api.buscavuelosbaratos.com`,
   publica el Worker y conecta el bot).
4. *Actions → Buscar ofertas y publicar → Run workflow* para la primera corrida.

## Workflows
| Workflow | Cuándo corre | Qué hace |
|---|---|---|
| `run.yml` — Buscar ofertas y publicar | cada hora (lo lanza Cloudflare), al subir código, manual; respaldo propio cada 6 h | pipeline completo + despliegue de la web |
| `worker.yml` — Desplegar alertas | al cambiar `worker/` o `config.yaml`, manual | pruebas, D1, Worker, claves y webhook del bot |
| `ejemplo.yml` — Publicar ejemplo en Telegram | manual | post de prueba con la mejor oferta de un país |

**Reloj en Cloudflare:** GitHub no garantiza sus corridas programadas (las retrasa o las descarta
sin avisar, sobre todo en repositorios nuevos). Por eso el Worker tiene un *Cron Trigger*
(`worker/wrangler.toml`, minuto 17 de cada hora) que le pide a GitHub correr `run.yml` por API.
Necesita el secret `GH_DISPATCH_TOKEN`.

El historial de precios (`historial.sqlite`) vive en la rama **`data`**, en un único commit que se
reemplaza en cada corrida para que el repositorio no crezca. La base se actualiza sola cuando se
agregan columnas nuevas.

## Leer el registro de una corrida (paso *Pipeline*)
```
Ofertas retiradas (nacionales, con muchas escalas o viajes cortos): 2
Tarifas obtenidas: 3691 · rutas internacionales: 1210
Ofertas nuevas: 7 (descartadas por precio no reciente: 3)
Ofertas terminadas en esta corrida: 2
Alertas activas: 40 · avisos enviados: 3 por Telegram, 1 por correo
Web generada con 25 ofertas activas
Frescura: {'match': 30, 'higher': 2, 'none': 5} · consultas: 37
Posts marcados como terminados en Telegram: 1
Publicadas en Telegram: {'general': 1, 'mexico': 2}
Verificación: este mes 120/1250 (serpapi 120/250, apify 0/1000) · hoy 9/57 · esta corrida {'ok': 2, 'rechazadas': 1, ...}
```
Si `Frescura` muestra `match` casi siempre en 0, la verificación de precios recientes no está
encontrando los viajes y no se publicará nada: revisar `bvb/fresh.py`.

## Probar en tu computadora (sin cuentas)
```bash
pip install -r requirements.txt pytest
BVB_MOCK=1 python -m bvb.main --no-social   # datos de prueba
cd site && python -m http.server 8000       # abre http://localhost:8000
python -m pytest -q                         # pruebas del buscador
cd worker && npm install && npm test        # pruebas del servidor de alertas
```

## Estructura
| Archivo | Qué hace |
|---|---|
| `config.yaml` | Países, ciudades, zonas horarias, reglas de oferta, cupos, frescura, alertas |
| `bvb/main.py` | Orquesta la corrida completa |
| `bvb/fetch.py` | Consulta `aviasales/v3/prices_for_dates` por origen y arma el enlace de afiliado |
| `bvb/refdata.py` | Nombres de ciudades, países, aerolíneas y coordenadas (Travelpayouts Data Files) |
| `bvb/deals.py` | Historial, mediana, reglas de oferta, filtros y anti-repetición |
| `bvb/fresh.py` | Verifica cuándo se vio cada precio y termina las ofertas que ya no se sostienen |
| `bvb/verify.py` | Verificación en vivo (SerpApi → Apify) con presupuesto mensual/diario/por hora; se verifican primero los precios más recientes (`verify.freshness_weight_hours`) |
| `bvb/copywriter.py` | Textos con Claude (Haiku) o plantilla |
| `bvb/site.py` + `templates/` | Web estática (portada, país, destino, oferta), sitemap, robots, CNAME |
| `bvb/telegram.py` | Canales general y por país, cupos, horario, edición de posts terminados |
| `bvb/alerts.py` | Avisos de alertas por ruta (Telegram y correo vía Resend) |
| `bvb/post_example.py` | Post de ejemplo por país |
| `worker/` | Servidor de alertas (Cloudflare Worker + D1) y sus pruebas |
| `static/` | Estilos y banderas (flag-icons, licencia MIT) |
| `tests/` | Pruebas del buscador |

## Pendientes / ideas
- Confirmar en Travelpayouts que el enlace de afiliado registra los clics (o usar su Links API).
- Páginas permanentes por ruta para SEO ("Vuelos baratos de San José a Madrid") con historial de precios.
- Ofertas complementarias en cada oferta: hotel, eSIM, seguro de viaje, tours.
- Imagen por oferta para compartir; Facebook/Instagram vía Graph API de Meta.
- Política de privacidad y términos (se guardan correos de alertas).
- Convertir el proyecto en plantilla para replicarlo en otros nichos.
