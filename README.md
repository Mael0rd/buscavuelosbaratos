# buscavuelosbaratos.com

Busca vuelos baratos desde Costa Rica, detecta ofertas reales contra el historial de precios,
genera la web estática y publica en Telegram. Corre solo cada 6 horas en GitHub Actions (gratis).

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

## Ajustes (config.yaml)
- `origins` / `destinations`: rutas a vigilar y precio tope de oferta mientras se acumula historial.
- `deals.drop_pct`: qué tan por debajo de la mediana debe estar (0.25 = 25%).
- Los primeros días se usa `max_price`; con ~8 observaciones por ruta pasa a usar la mediana real.

## Estructura
| Archivo | Qué hace |
|---|---|
| `bvb/fetch.py` | Consulta `aviasales/v3/prices_for_dates` y arma el enlace de afiliado |
| `bvb/deals.py` | Historial, mediana, reglas de oferta y anti-repetición |
| `bvb/copywriter.py` | Textos con Claude (Haiku) o plantilla |
| `bvb/site.py` + `templates/` | Web estática, sitemap, robots, CNAME |
| `bvb/telegram.py` | Publica ofertas pendientes en el canal |
| `.github/workflows/run.yml` | Programación cada 6 h + despliegue a Pages |

## Siguientes pasos sugeridos
- Facebook/Instagram vía Graph API de Meta (requiere página de negocio y app aprobada).
- Imagen por oferta (tarjeta generada con Pillow) para redes.
- Página por destino (`/destino/madrid`) para SEO.
- Replicar a otro nicho: cambiar `fetch.py` y los textos; el resto se reutiliza.
