# Watcher de propiedades apto crédito (Remax + Zonaprop + Argenprop)

- **Fecha:** 2026-06-06
- **Repo:** `mudarme-bot`
- **Estado:** Diseño aprobado (pendiente review del spec)

## Contexto

Tenemos dos proyectos relacionados:

- **`bot_bna_hogares`**: watcher del portal +Hogares (BNA). Consume una **API JSON limpia**
  (`mashogaresconbna.com.ar/api/propiedades`) por cada "búsqueda guardada" (URL con filtros),
  aplica filtros post-API (antigüedad, superficie, localidad, reservadas), deduplica por `id`
  en SQLite y notifica por Telegram. Todo el sitio +Hogares es inherentemente "apto crédito".

- **`mudarme-bot`**: scraper de inmuebles multi-sitio. Patrón **gateway + parser + factory**
  por sitio (`scraper_app/gateways/*`, `scraper_app/parsers/*`, `scraper_app/services.py`),
  modelo `Posting` (SQLModel/SQLite), dedup por `sha`, envío a Telegram con reintentos
  (`telegram_app`), loop persistente en `main.py`. Sitios ya soportados: **Zonaprop, Argenprop,
  MercadoLibre, Properati, La Voz**. El filtrado se hace **solo por la URL de búsqueda** que
  arma el usuario (no hay filtros post-scrape). Los requests usan `cloudscraper` (maneja
  anti-bot tipo Cloudflare).

## Objetivo

Replicar la idea del watcher de +Hogares pero para **Remax, Zonaprop y Argenprop**, con foco en
publicaciones **apto crédito**, reusando la infraestructura de `mudarme-bot`. Las publicaciones
nuevas llegan a un grupo de Telegram propio de `mudarme-bot`, **separado** del de `bot_bna_hogares`.

## Decisiones

1. **Hogar:** vive en `mudarme-bot`. Se reusa todo: gateway/parser/factory, modelo `Posting`,
   dedup por `sha`, Telegram con reintentos, loop persistente.
2. **Filtrado por URL, a mano:** **no** se construye capa de filtros post-scrape. Zona, precio,
   ambientes, antigüedad y **apto crédito** se aplican en el buscador de cada sitio y viajan en
   la URL que el usuario pega en el config. (Confirmado por el usuario: estos sitios permiten
   filtrar antigüedad y apto crédito por URL.)
3. **Telegram:** se usa el **mismo bot + grupo** de `mudarme-bot` (config en runtime). No se toca
   `bot_bna_hogares`.
4. **Remax vía API JSON (opción A):** se le pega directo a la API JSON interna de Remax (estilo
   `bot_bna_hogares`), no se parsea HTML renderizado. Más robusto ante cambios de CSS.

## Alcance

**Incluye:**
- Nuevo `RemaxGateway` + `RemaxParser` (lee JSON) + `build_for_remax` en la factory + `remax_full_url`
  en el `Config`/`main.py`.
- `config.example.yaml` nuevo en el repo documentando todos los campos (hoy no existe).
- Pasada de **verificación en vivo** de Zonaprop y Argenprop, arreglando selectores rotos.
- Tests del `RemaxParser` contra fixture JSON + smoke test en vivo de cada gateway.

**No incluye (YAGNI):**
- Capa de filtros post-scrape (antigüedad/superficie/localidad en código).
- Playwright/navegador headless como base (solo fallback si cloudscraper no alcanza).
- Tocar MercadoLibre, Properati, La Voz, ni `bot_bna_hogares`.

## Arquitectura

### Se reusa sin cambios
- `posting_app/database.py` — modelo `Posting` (sha, url, title, price, location, description, sent)
  y `PostingRepository` (dedup por `sha`, no-enviados, marcar enviado).
- `telegram_app/services.py` — envío con reintentos/backoff.
- `main.py` — loop persistente y orquestación (se le agrega el bloque de Remax).

### Componentes nuevos

**`RemaxGateway(BaseGateway)`** — `scraper_app/gateways/remax.py`
- Usa `cloudscraper` (heredado de `BaseGateway.make_request`) para `GET` la URL de la API de Remax.
- Devuelve el **cuerpo JSON como texto** (el parser lo deserializa). `make_request` ya devuelve
  `res.text`; el parser hace `json.loads`.
- Paginación con el mecanismo existente del `{}` en la URL, aplicado al parámetro `page` de la API
  (ej. `...&page={}&pageSize=...`). `pages` viene del `Config`.

**`RemaxParser(BaseParser)`** — `scraper_app/parsers/remax.py`
- Recibe el JSON y recorre la lista de publicaciones (la ruta exacta dentro del JSON —p. ej.
  `data` / `content` / `results`— se determina con la respuesta real; ver "Inputs necesarios").
- Por cada item arma un `Posting`:
  - `sha`: del `id` del listing (o de la URL pública vía `get_id`), para dedup estable.
  - `url`: link público a la publicación en remax.com.ar.
  - `title`, `price`, `location`, `description` (m²/ambientes/dormitorios).
- Respeta el dedup: si `PostingRepository.get_posting_by_sha(sha)` ya existe, lo saltea.

**Factory** — `scraper_app/services.py`
- `PostingServiceFactory.build_for_remax(pages, full_url)` que arma `RemaxGateway` + `RemaxParser`,
  siguiendo el patrón de `build_for_zonaprop`/`build_for_argenprop`.

**Config** — `main.py`
- Agregar `remax_full_url: Optional[str] = None` al modelo `Config`.
- Agregar el bloque `if config.remax_full_url: ... build_for_remax(...).scrap_and_create_postings()`.

### Flujo de datos
URL de búsqueda (con filtros + apto crédito, provista por el usuario) → `RemaxGateway` (cloudscraper,
paginado) → JSON → `RemaxParser` → `Posting` deduplicado → SQLite → `main.py` toma no-enviados →
Telegram (grupo de mudarme-bot).

## Riesgos

1. **Scrapers stale:** `mudarme-bot` no se usa hace meses. Zonaprop (clases ofuscadas tipo
   `postingCardLayout-module__...`) y Argenprop probablemente requieran arreglo de selectores.
   La verificación en vivo es parte del trabajo, no un extra.
2. **Anti-bot:** Zonaprop y Remax responden 403 a requests planos. `cloudscraper` ayuda; si no
   alcanza para Zonaprop (DataDome es agresivo), el fallback es Playwright (fuera de alcance base).
3. **Endpoint de Remax desconocido:** el host viejo `api.redremax.com` ya no resuelve y el sitio
   bloquea herramientas automáticas. La URL exacta de la API la provee el usuario desde
   F12 → Network. La forma del JSON (rutas de campos) se cierra contra la respuesta real.

## Verificación / Testing

- **Unit:** `RemaxParser` contra un fixture JSON guardado (respuesta real recortada) → valida que
  arma `Posting` con los campos correctos y respeta dedup.
- **Smoke en vivo:** correr cada gateway (Remax, Zonaprop, Argenprop) con una URL real y confirmar
  que devuelve publicaciones parseadas (no 403/lista vacía).
- **End-to-end:** una corrida de `main.py` que mande al menos un mensaje de prueba al grupo nuevo.

## Inputs necesarios del usuario (para implementación/test)

1. **Telegram:** `bot_token` + `chat_id` del grupo nuevo (crear bot y grupo si no existen).
2. **URLs ya filtradas (con apto crédito aplicado):**
   - **Zonaprop** y **Argenprop:** URL de la búsqueda con la página reemplazada por `{}`
     (`...-pagina-{}.html`).
   - **Remax:** URL del request a la API desde F12 → Network → Fetch/XHR (con `page` reemplazable
     por `{}`). Si no, la URL del navegador y se investiga en implementación.
3. Confirmación de si Zonaprop/Argenprop traían resultados la última vez (para dimensionar el arreglo).

## Workflow de implementación

1. Opus escribe spec (este doc) + plan granular (skill `writing-plans`).
2. Sonnet ejecuta el plan (sesión aparte para ahorrar tokens, o subagente).
3. Opus revisa el diff (skill de code-review), corre tests + smoke en vivo, e itera.
