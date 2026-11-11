# buscavuelosbaratos.com

Busca vuelos baratos saliendo desde 19 países de Hispanoamérica (33 ciudades) hacia cualquier destino,
detecta ofertas reales contra el historial de precios de cada ruta, genera la web por país y publica
en Telegram. Corre solo cada hora en GitHub Actions (gratis).

El historial de precios se guarda en la rama `data` (un único commit que se reemplaza en cada corrida).

```
Travelpayouts API → SQLite (historial) → detector de ofertas → textos (Claude o plantilla)
                                                     ├→ web estática (GitHub Pages + tu dominio)
                                                     └→ canal de Telegram
```

## Probar en tu computadora (sin cuentas)
```bash
pip install -r requirements.txt
BVB_MOCK=1 python -m bvb.main --no-social
cd site && python -m http.server 8000    # abre http://localhost:8000
python -m pytest -q
```

## Puesta en marcha real
1. **Travelpayouts**: regístrate, únete al programa **Aviasales** y copia tu *API token* y tu *marker*.
   Verifica en su generador de enlaces que el formato de `affiliate_link()` (bvb/fetch.py) registra tus clics.
2. **Telegram**: crea un bot con @BotFather, crea el canal y agrega el bot como administrador.
3. **GitHub**: sube este proyecto a un repo nuevo. En *Settings → Secrets and variables → Actions*:
   - Secrets: `TRAVELPAYOUTS_TOKEN`, `TRAVELPAYOUTS_MARKER`, `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY` (opcional)
   - Variables: `TELEGRAM_CHANNEL` (ej. `@buscavuelosbaratos`)
4. **GitHub Pages**: *Settings → Pages → Source: GitHub Actions*. Custom domain: `buscavuelosbaratos.com`.
5. **DNS del dominio**: registros A hacia las IP de GitHub Pages (185.199.108.153, .109.153, .110.153, .111.153)
   y un CNAME `www` → `<tu-usuario>.github.io`. Activa "Enforce HTTPS".
6. Ve a *Actions → Buscar ofertas y publicar → Run workflow* para la primera corrida.

## Precios honestos y ofertas terminadas
- Antes de publicar se consulta `/v2/prices/latest` de la ruta para saber cuándo se vio ese viaje
  (`found_at`). Solo se publica si se vio hace menos de `freshness.max_age_hours` (6 h).
- Cada corrida revisa las ofertas publicadas: si el precio subió, no se reconfirma en 24 h o la salida
  está muy cerca, la oferta termina: sale de las listas, su página muestra el aviso y el bot edita el
  post de Telegram ("❌ OFERTA TERMINADA").

## Canales de Telegram
- Canal general: variable `TELEGRAM_CHANNEL` (1 post por hora, máx. 10 al día).
- Canal por país: variable `TELEGRAM_CHANNEL_<PAÍS>`, p. ej. `TELEGRAM_CHANNEL_MEXICO`,
  `TELEGRAM_CHANNEL_COSTA_RICA` (2 por hora, máx. 10 al día). No se publica de 23:00 a 6:00.

## Alertas por ruta (Telegram y correo)
Las personas crean alertas origen → destino desde `/alertas.html` (correo, con confirmación) o
hablando con el bot de Telegram (`/alerta`, `/misalertas`). Se avisa solo cuando la ruta pasa
la regla de oferta, sin repetir el aviso en 7 días salvo que baje otro 10%.

- `worker/`: servidor de alertas en Cloudflare Workers + D1 (`api.buscavuelosbaratos.com`).
  Lo despliega el workflow **Desplegar alertas**. Pruebas: `cd worker && npm install && npm test`.
- `bvb/alerts.py`: en cada corrida lee las alertas activas y envía los avisos (Telegram / Resend).
- Secrets necesarios: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `RESEND_API_KEY`
  (más `TELEGRAM_BOT_TOKEN`, que ya existe).

## Ajustes (config.yaml)
- `countries`: países (secciones de la web) y sus ciudades de salida.
- `deals.drop_pct`: qué tan por debajo de la mediana de la ruta debe estar (0.30 = 30%).
- `deals.cold_start`: tope por distancia mientras una ruta tiene menos de `min_days` días de historial.
- `social.max_per_run`: máximo de posts en Telegram por corrida (el resto queda solo en la web).

## Estructura
| Archivo | Qué hace |
|---|---|
| `bvb/fetch.py` | Consulta `aviasales/v3/prices_for_dates` por origen (todos los destinos) |
| `bvb/refdata.py` | Nombres de ciudades, países, aerolíneas y coordenadas (Travelpayouts Data Files) |
| `bvb/deals.py` | Historial, mediana, reglas de oferta y anti-repetición |
| `bvb/copywriter.py` | Textos con Claude (Haiku) o plantilla |
| `bvb/site.py` + `templates/` | Web estática, sitemap, robots, CNAME |
| `bvb/telegram.py` | Publica ofertas pendientes en el canal (formato con botones) |
| `bvb/alerts.py` | Avisos de alertas por ruta (Telegram y correo) |
| `worker/` | Servidor de alertas (bot de Telegram, formulario, confirmación y bajas) |
| `.github/workflows/run.yml` | Programación cada 6 h + despliegue a Pages |

## Siguientes pasos sugeridos
- Facebook/Instagram vía Graph API de Meta (requiere página de negocio y app aprobada).
- Imagen por oferta (tarjeta generada con Pillow) para redes.
- Página por destino (`/destino/madrid`) para SEO.
- Replicar a otro nicho: cambiar `fetch.py` y los textos; el resto se reutiliza.
