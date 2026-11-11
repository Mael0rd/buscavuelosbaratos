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
| Precio bajo lo normal (con ≥ 7 días de historial de la ruta) | ≥ 30% bajo la mediana | `deals.drop_pct`, `deals.min_days` |
| Precio bajo lo normal (rutas sin historial aún) | tope por distancia **y** 25% bajo los otros meses | `deals.cold_start` |
| Precio reciente (mismo viaje visto hace poco) | < 6 h | `freshness.max_age_hours` |
| No repetida | misma ruta no antes de 7 días, salvo que baje otro 10% | `deals.repost_*` |

### Precios honestos y ofertas terminadas
La API de datos devuelve precios vistos por usuarios de Aviasales en las últimas 48 h, sin decir
cuándo. Por eso, antes de publicar se consulta `/v2/prices/latest` de la ruta, que sí trae `found_at`,
y se busca el mismo viaje (mismas fechas). En la web y en Telegram se muestra **"Precio visto hace X"**.

Cada corrida revisa las ofertas publicadas. Una oferta **termina** si el precio subió, si no se
reconfirma en 24 h (`freshness.stale_hours`) o si la salida está a menos de 2 días. Al terminar:
sale de las listas, su página muestra "❌ Esta oferta terminó" (sin botón de reservar) y el bot
**edita el post de Telegram** para indicarlo.

## La web
- **Portada** con una sección por país. El país del visitante (detectado por la zona horaria o el
  idioma del navegador, sin servicios externos) aparece primero con "📍 Tu país".
- **`/pais/<país>.html`**: todas las ofertas de ese país + botón para unirse a su canal de Telegram.
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
| `run.yml` — Buscar ofertas y publicar | cada hora (minuto 17), al subir código, manual | pipeline completo + despliegue de la web |
| `worker.yml` — Desplegar alertas | al cambiar `worker/` o `config.yaml`, manual | pruebas, D1, Worker, claves y webhook del bot |
| `ejemplo.yml` — Publicar ejemplo en Telegram | manual | post de prueba con la mejor oferta de un país |

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
| `bvb/copywriter.py` | Textos con Claude (Haiku) o plantilla |
| `bvb/site.py` + `templates/` | Web estática, sitemap, robots, CNAME |
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
