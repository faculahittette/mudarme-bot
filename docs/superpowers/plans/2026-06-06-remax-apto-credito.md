# Watcher apto crédito (Remax + Zonaprop + Argenprop) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar Remax (vía su API JSON) al scraper `mudarme-bot` y dejar verificados Zonaprop/Argenprop, para que las publicaciones nuevas (filtradas por URL, incluido apto crédito) lleguen al grupo de Telegram de mudarme-bot.

**Architecture:** Se reusa el patrón existente gateway/parser/factory + `Posting`/SQLite + Telegram + loop de `main.py`. Remax se suma como un gateway que baja JSON (con `cloudscraper`) y un parser que lo deserializa, conviviendo con los parsers HTML. No se construye capa de filtros: todo se filtra en la URL.

**Tech Stack:** Python, cloudscraper, BeautifulSoup (otros sitios), SQLModel/SQLite, Typer, Rich, pytest.

**Branch:** `feat/apto-credito` (ya creada y activa).

**Setup previo a cada sesión:** activar el venv del repo:
- Windows PowerShell: `.\venv\Scripts\Activate.ps1`
- bash: `source venv/Scripts/activate`
Todos los comandos `python`/`pytest` asumen el venv activo y el cwd en la raíz del repo.

---

## Mapa de archivos

**Nuevos:**
- `scraper_app/gateways/remax.py` — `RemaxGateway` (baja JSON, paginación 0-indexed).
- `scraper_app/parsers/remax.py` — `RemaxParser` (deserializa JSON → `Posting`).
- `tests/test_pagination.py` — paginación respeta `first_page` del gateway.
- `tests/test_remax_parser.py` — parseo de Remax contra fixture.
- `tests/fixtures/remax_sample.json` — respuesta JSON representativa de Remax.
- `config.example.yaml` — config documentada (hoy no existe).

**Modificados:**
- `scraper_app/gateways/base.py` — atributo `first_page = 1`.
- `scraper_app/services.py` — `ScraperService` usa `first_page`; `ScraperServiceFactory.build_for_remax`.
- `scraper_app/gateways/__init__.py` y `scraper_app/parsers/__init__.py` — export de Remax.
- `posting_app/services.py` — `PostingServiceFactory.build_for_remax`.
- `main.py` — campo `remax_full_url` + bloque de scrap; fix import de `ValidationError`.
- `requirements.txt` — agregar `pytest`.

---

## Task 0: Setup de tests + chequeo de import

**Files:**
- Modify: `requirements.txt`
- Create: `tests/fixtures/.gitkeep`

- [ ] **Step 1: Agregar pytest a requirements.txt**

Agregar al final de `requirements.txt` (en su propia línea):

```
pytest==8.2.0
```

- [ ] **Step 2: Instalar**

Run: `pip install -r requirements.txt`
Expected: instala pytest sin errores.

- [ ] **Step 3: Crear carpeta de fixtures**

Run (bash): `mkdir -p tests/fixtures && touch tests/fixtures/.gitkeep`

- [ ] **Step 4: Chequear que `main.py` importa (detecta breakage por deps viejas)**

Run: `python -c "import main"`
Expected: sin salida (éxito). Si falla con `ModuleNotFoundError: pydantic.error_wrappers` o similar, NO lo arregles acá: se corrige en Task 5 (Step de import). Anotá el error y seguí.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/fixtures/.gitkeep
git commit -m "chore: add pytest and tests fixtures dir

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 1: Soporte de offset de paginación (`first_page`)

La API de Remax usa `page=0` como primera página. `ScraperService` hoy itera `range(1, pages+1)`. Agregamos `first_page` al gateway (default 1, retrocompatible) y lo usamos en el loop.

**Files:**
- Modify: `scraper_app/gateways/base.py`
- Modify: `scraper_app/services.py` (método `get_postings_from_scraper`)
- Test: `tests/test_pagination.py`

- [ ] **Step 1: Escribir el test que falla**

Create `tests/test_pagination.py`:

```python
from scraper_app.services import ScraperService


class _FakeGateway:
    paginated = True

    def __init__(self, first_page):
        self.first_page = first_page
        self.requested = []

    def make_request(self, url):
        self.requested.append(url)
        return ''


class _FakeParser:
    def get_soup_object(self, html):
        pass

    def extract_data(self):
        return set()


def test_first_page_zero_indexed():
    gw = _FakeGateway(first_page=0)
    svc = ScraperService(pages=3, url='http://x?page={}', gateway=gw, parser=_FakeParser())
    svc.get_postings_from_scraper()
    assert gw.requested == ['http://x?page=0', 'http://x?page=1', 'http://x?page=2']


def test_first_page_one_indexed_default():
    gw = _FakeGateway(first_page=1)
    svc = ScraperService(pages=2, url='http://x?page={}', gateway=gw, parser=_FakeParser())
    svc.get_postings_from_scraper()
    assert gw.requested == ['http://x?page=1', 'http://x?page=2']
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_pagination.py -v`
Expected: `test_first_page_zero_indexed` FALLA (hoy el loop arranca en 1, pediría `page=1,2,3`).

- [ ] **Step 3: Agregar `first_page` a `BaseGateway`**

En `scraper_app/gateways/base.py`, dentro de `class BaseGateway(ABC):`, junto a `paginated = True`, agregar:

```python
    first_page = 1
```

- [ ] **Step 4: Usar `first_page` en `ScraperService`**

En `scraper_app/services.py`, método `get_postings_from_scraper`, reemplazar:

```python
        pages = self._pages if self._gateway.paginated else 1

        for page in range(1, pages + 1):
```

por:

```python
        pages = self._pages if self._gateway.paginated else 1
        first_page = getattr(self._gateway, 'first_page', 1)

        for page in range(first_page, first_page + pages):
```

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_pagination.py -v`
Expected: ambos PASAN.

- [ ] **Step 6: Commit**

```bash
git add scraper_app/gateways/base.py scraper_app/services.py tests/test_pagination.py
git commit -m "feat: gateway-controlled pagination offset (first_page)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `RemaxGateway`

**Files:**
- Create: `scraper_app/gateways/remax.py`
- Modify: `scraper_app/gateways/__init__.py`

- [ ] **Step 1: Crear el gateway**

Create `scraper_app/gateways/remax.py`:

```python
from .base import BaseGateway


class RemaxGateway(BaseGateway):
    # La API de Remax pagina con page=0 como primera pagina (0-indexed).
    first_page = 0

    def __init__(self):
        self._name = 'Remax'
```

- [ ] **Step 2: Exportarlo**

En `scraper_app/gateways/__init__.py`, agregar al final:

```python
from .remax import RemaxGateway
```

- [ ] **Step 3: Verificar import**

Run: `python -c "from scraper_app.gateways import RemaxGateway; print(RemaxGateway().first_page)"`
Expected: imprime `0`.

- [ ] **Step 4: Commit**

```bash
git add scraper_app/gateways/remax.py scraper_app/gateways/__init__.py
git commit -m "feat: add RemaxGateway (JSON, 0-indexed pagination)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `RemaxParser` (JSON → Posting)

> **NOTA DE REALIDAD:** las claves del JSON (`data.data[]`, `slug`, `price.amount`, `displayAddress`, `totalBuiltSurface`, `roomQuantity`, `bedroomQuantity`) son una forma **representativa** de la API de Remax. El fixture de este task ES el contrato contra el que se programa. La reconciliación con la respuesta REAL (que provee el usuario) está en **Task 7**.

**Files:**
- Create: `tests/fixtures/remax_sample.json`
- Create: `tests/test_remax_parser.py`
- Create: `scraper_app/parsers/remax.py`
- Modify: `scraper_app/parsers/__init__.py`

- [ ] **Step 1: Crear el fixture**

Create `tests/fixtures/remax_sample.json`:

```json
{
  "data": {
    "data": [
      {
        "id": 1001,
        "slug": "depto-3-amb-caballito-apto-credito",
        "title": "Departamento 3 ambientes en Caballito",
        "displayAddress": "Caballito, Capital Federal",
        "price": {"currency": "USD", "amount": 150000},
        "totalBuiltSurface": 68,
        "roomQuantity": 3,
        "bedroomQuantity": 2
      },
      {
        "id": 1002,
        "slug": "ph-villa-urquiza",
        "title": "PH en Villa Urquiza",
        "displayAddress": "Villa Urquiza, Capital Federal",
        "price": {"currency": "USD", "amount": 175000},
        "totalBuiltSurface": 80,
        "roomQuantity": 4,
        "bedroomQuantity": 3
      }
    ],
    "total": 2,
    "page": 0
  }
}
```

- [ ] **Step 2: Escribir el test que falla**

Create `tests/test_remax_parser.py`:

```python
from pathlib import Path

from scraper_app.parsers.remax import RemaxParser

FIXTURE = Path(__file__).parent / 'fixtures' / 'remax_sample.json'


def test_remax_parser_extracts_postings(monkeypatch):
    # Aislar del SQLite real: ningun sha existe todavia.
    monkeypatch.setattr(
        'scraper_app.parsers.remax.PostingRepository.get_posting_by_sha',
        lambda self, sha: None,
    )

    parser = RemaxParser()
    parser.get_soup_object(html=FIXTURE.read_text(encoding='utf-8'))
    postings = parser.extract_data()

    assert len(postings) == 2
    by_url = {p.url: p for p in postings}

    p = by_url['https://www.remax.com.ar/listings/depto-3-amb-caballito-apto-credito']
    assert p.title == 'Departamento 3 ambientes en Caballito'
    assert p.location == 'Caballito, Capital Federal'
    assert 'USD' in p.price
    assert '68 m' in p.description
    assert p.sha


def test_remax_parser_skips_seen(monkeypatch):
    # Si el repo dice que ya existe, no se incluye.
    monkeypatch.setattr(
        'scraper_app.parsers.remax.PostingRepository.get_posting_by_sha',
        lambda self, sha: object(),
    )
    parser = RemaxParser()
    parser.get_soup_object(html=FIXTURE.read_text(encoding='utf-8'))
    assert parser.extract_data() == set()


def test_remax_parser_handles_bad_json(monkeypatch):
    monkeypatch.setattr(
        'scraper_app.parsers.remax.PostingRepository.get_posting_by_sha',
        lambda self, sha: None,
    )
    parser = RemaxParser()
    parser.get_soup_object(html='<html>403 Forbidden</html>')
    assert parser.extract_data() == set()
```

- [ ] **Step 3: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_remax_parser.py -v`
Expected: FALLA con `ModuleNotFoundError: scraper_app.parsers.remax`.

- [ ] **Step 4: Implementar el parser**

Create `scraper_app/parsers/remax.py`:

```python
import json
from typing import Set

from .base import BaseParser
from posting_app.database import Posting, PostingRepository


class RemaxParser(BaseParser):
    _base_url = 'https://www.remax.com.ar'

    def get_soup_object(self, html: str):
        '''La respuesta de Remax es JSON, no HTML: guardamos el texto crudo.'''
        self._raw = html

    def _iter_listings(self, payload):
        '''Devuelve la lista de publicaciones tolerando variantes del contenedor.
        Ajustar contra la respuesta real (ver Task 7).'''
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            data = payload.get('data', payload)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get('data') or data.get('content') or data.get('results') or []
        return []

    def _format_price(self, price_obj) -> str:
        if isinstance(price_obj, dict):
            currency = price_obj.get('currency') or ''
            amount = price_obj.get('amount')
            if amount is not None:
                return '{} {:,}'.format(currency, amount).strip()
            return self.sanitize_text(currency)
        return self.sanitize_text(str(price_obj or ''))

    def extract_data(self) -> Set[Posting]:
        postings = set()
        try:
            payload = json.loads(self._raw) if getattr(self, '_raw', '') else {}
        except (ValueError, TypeError):
            return postings

        posting_repository = PostingRepository()

        for item in self._iter_listings(payload):
            if not isinstance(item, dict):
                continue

            slug = item.get('slug') or ''
            listing_id = str(item.get('id') or '')
            if slug:
                href = '{}/listings/{}'.format(self._base_url, slug)
            elif listing_id:
                href = '{}/listings/{}'.format(self._base_url, listing_id)
            else:
                continue

            sha = self.get_id(href)
            if posting_repository.get_posting_by_sha(sha):
                continue

            title = self.sanitize_text(item.get('title') or '')[:100]
            price = self._format_price(item.get('price'))
            location = self.sanitize_text(item.get('displayAddress') or '')

            features = []
            if item.get('totalBuiltSurface'):
                features.append('{} m2'.format(item['totalBuiltSurface']))
            if item.get('roomQuantity'):
                features.append('{} amb'.format(item['roomQuantity']))
            if item.get('bedroomQuantity'):
                features.append('{} dorm'.format(item['bedroomQuantity']))
            description = ' | '.join(features)

            postings.add(Posting(
                sha=sha,
                url=href,
                title=title,
                price=price,
                description=description,
                location=location,
            ))

        return postings
```

- [ ] **Step 5: Exportar el parser**

En `scraper_app/parsers/__init__.py`, agregar al final:

```python
from .remax import RemaxParser
```

- [ ] **Step 6: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_remax_parser.py -v`
Expected: los 3 tests PASAN.

- [ ] **Step 7: Commit**

```bash
git add scraper_app/parsers/remax.py scraper_app/parsers/__init__.py tests/test_remax_parser.py tests/fixtures/remax_sample.json
git commit -m "feat: add RemaxParser (JSON) with tests against fixture

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Wiring de la factory

**Files:**
- Modify: `scraper_app/services.py` (`ScraperServiceFactory`)
- Modify: `posting_app/services.py` (`PostingServiceFactory`)

- [ ] **Step 1: Importar Remax en `scraper_app/services.py`**

En `scraper_app/services.py`, en el import de gateways agregar `RemaxGateway` y en el de parsers agregar `RemaxParser`:

```python
from .gateways import (
    ArgenpropGateway,
    BaseGateway,
    LaVozGateway,
    MercadolibreGateway,
    ProperatiGateway,
    RemaxGateway,
    ZonapropGateway,
)
from .parsers import (
    ArgenpropParser,
    BaseParser,
    LaVozParser,
    MercadolibreParser,
    ProperatiParser,
    RemaxParser,
    ZonapropParser,
)
```

- [ ] **Step 2: Agregar `build_for_remax` en `ScraperServiceFactory`**

En `scraper_app/services.py`, dentro de `class ScraperServiceFactory:`, agregar:

```python
    @classmethod
    def build_for_remax(
        cls,
        pages: int,
        full_url: str
    ) -> ScraperService:
        return ScraperService(
            pages=pages,
            url=full_url,
            gateway=RemaxGateway(),
            parser=RemaxParser(),
        )
```

- [ ] **Step 3: Agregar `build_for_remax` en `PostingServiceFactory`**

En `posting_app/services.py`, dentro de `class PostingServiceFactory:`, agregar:

```python
    @classmethod
    def build_for_remax(
        cls,
        pages: int,
        full_url: str
    ) -> PostingService:
        scrapper_service = ScraperServiceFactory.build_for_remax(
            pages=pages,
            full_url=full_url,
        )
        return PostingService(scraper_service=scrapper_service)
```

- [ ] **Step 4: Verificar wiring**

Run: `python -c "from posting_app.services import PostingServiceFactory; s = PostingServiceFactory.build_for_remax(pages=1, full_url='http://x?page={}'); print(type(s).__name__)"`
Expected: imprime `PostingService`.

- [ ] **Step 5: Commit**

```bash
git add scraper_app/services.py posting_app/services.py
git commit -m "feat: wire Remax into scraper and posting factories

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `main.py` — config y bloque de scrap

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Fix del import de `ValidationError` (pydantic v2)**

En `main.py` reemplazar:

```python
from pydantic.error_wrappers import ValidationError
```

por:

```python
from pydantic import ValidationError
```

- [ ] **Step 2: Agregar el campo `remax_full_url` al `Config`**

En `main.py`, dentro de `class Config(BaseModel):`, agregar (junto a los otros `*_full_url`):

```python
    remax_full_url: Optional[str] = None
```

- [ ] **Step 3: Agregar el bloque de scrap de Remax**

En `main.py`, dentro del `while(True):`, después del bloque de `properati` y antes de `console.log('Postings scrapped', ...)`, agregar:

```python
        if config.remax_full_url:
            remax_posting_service = PostingServiceFactory.build_for_remax(
                pages=config.pages,
                full_url=config.remax_full_url,
            )
            remax_posting_service.scrap_and_create_postings()
```

- [ ] **Step 4: Verificar que importa**

Run: `python -c "import main; print(main.Config.model_fields.keys())"`
Expected: la lista de campos incluye `remax_full_url` y NO hay error de import.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: add remax_full_url config and scrap block; fix pydantic import

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: `config.example.yaml`

**Files:**
- Create: `config.example.yaml`

- [ ] **Step 1: Crear el ejemplo de config**

Create `config.example.yaml`:

```yaml
# Copia este archivo a config.yaml y completalo. Pasalo a main.py:
#   python main.py config.yaml

# Cuantas paginas recorrer por sitio (la primera pagina trae lo mas nuevo).
pages: 3

# Segundos de espera entre corridas cuando persist: true.
sleep_time: 300

# Bot de Telegram (grupo de mudarme-bot, separado de bot_bna_hogares).
bot_token: "TU_TOKEN_DE_BOT"
chat_room: "TU_CHAT_ID"

# true = loop infinito; false = una sola corrida.
persist: false

# URLs de busqueda YA filtradas (zona, precio, ambientes, antiguedad, apto credito).
# Reemplazar el numero de pagina por {}.
# Comenta (o deja en null) las que no uses.

# Zonaprop/Argenprop: la URL del navegador con la pagina como {} (ej: ...-pagina-{}.html)
zonaprop_full_url: null
argenprop_full_url: null

# Remax: la URL del request a la API (F12 -> Network -> Fetch/XHR), con page={} (0-indexed).
remax_full_url: null

# Otros sitios soportados (opcionales):
mercadolibre_full_url: null
la_voz_full_url: null
properati_full_url: null
```

- [ ] **Step 2: Commit**

```bash
git add config.example.yaml
git commit -m "docs: add config.example.yaml documenting all fields incl. remax

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Reconciliar el parser de Remax con la API real (REQUIERE INPUT DEL USUARIO)

> **GATE:** este task necesita la **URL real de la API de Remax** (F12 → Network → Fetch/XHR, con apto crédito aplicado) y una **muestra de la respuesta JSON**. Si todavía no están, detené acá y pedíselas al usuario. No inventes la estructura.

**Files:**
- Modify (si hace falta): `scraper_app/parsers/remax.py`, `tests/fixtures/remax_sample.json`

- [ ] **Step 1: Capturar la respuesta real**

Con la URL provista, guardá la respuesta cruda (con la primera página, `page=0`):

```bash
python -c "from scraper_app.gateways import RemaxGateway; print(RemaxGateway().make_request(url='LA_URL_REAL_CON_page=0'))" > /tmp/remax_real.json
head -c 2000 /tmp/remax_real.json
```

Expected: JSON (no `403`/HTML). Si vuelve 403 o vacío, cloudscraper no alcanza → ver "Riesgos" del spec (posible fallback Playwright, fuera de alcance base): reportar al usuario y frenar.

- [ ] **Step 2: Reconciliar claves**

Comparar la estructura real con el fixture/parsing. Ajustar en `scraper_app/parsers/remax.py`:
- `_iter_listings`: la ruta real al array de publicaciones.
- nombres de campos: link/slug, `title`, precio (moneda+monto), dirección/ubicación, superficie, ambientes, dormitorios.
Actualizar `tests/fixtures/remax_sample.json` para que refleje la forma real (recortado a 2 items).

- [ ] **Step 3: Correr los tests del parser**

Run: `python -m pytest tests/test_remax_parser.py -v`
Expected: PASAN con el fixture reconciliado.

- [ ] **Step 4: Smoke en vivo de Remax**

```bash
python -c "from scraper_app.parsers.remax import RemaxParser; from scraper_app.gateways import RemaxGateway; p=RemaxParser(); p.get_soup_object(RemaxGateway().make_request('LA_URL_REAL_CON_page=0')); ps=p.extract_data(); print(len(ps)); [print(x.title, '|', x.price, '|', x.location, '|', x.url) for x in list(ps)[:3]]"
```
Expected: cantidad > 0 y títulos/precios/links coherentes.

- [ ] **Step 5: Commit**

```bash
git add scraper_app/parsers/remax.py tests/fixtures/remax_sample.json
git commit -m "fix: reconcile RemaxParser with live API response

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Verificar/arreglar Zonaprop y Argenprop en vivo

> Como mudarme-bot no se usa hace meses, los selectores pueden estar rotos. Esto es investigación + arreglo puntual, no TDD.

**Files:**
- Modify (si hace falta): `scraper_app/parsers/zonaprop.py`, `scraper_app/parsers/argenprop.py`

- [ ] **Step 1: Smoke de Zonaprop (necesita una URL real con `{}`)**

```bash
python -c "from scraper_app.parsers.zonaprop import ZonapropParser; from scraper_app.gateways import ZonapropGateway; p=ZonapropParser(); p.get_soup_object(ZonapropGateway().make_request('URL_ZONAPROP_pagina-{}.html'.format(1))); ps=p.extract_data(); print('postings:', len(ps)); [print(x.title,'|',x.price,'|',x.url) for x in list(ps)[:3]]"
```
Expected: `postings: > 0`.
- Si es 0 o hay error: el gateway respondió 403/captcha, o cambiaron las clases CSS. Bajar el HTML a un archivo, inspeccionar las clases reales de las tarjetas y actualizar `base_info_class` / selectores en `scraper_app/parsers/zonaprop.py`. Si es 403 persistente, reportar (posible Playwright, fuera de alcance).

- [ ] **Step 2: Smoke de Argenprop (misma idea, URL real con `{}`)**

```bash
python -c "from scraper_app.parsers.argenprop import ArgenpropParser; from scraper_app.gateways import ArgenpropGateway; p=ArgenpropParser(); p.get_soup_object(ArgenpropGateway().make_request('URL_ARGENPROP_con_{}'.format(1))); ps=p.extract_data(); print('postings:', len(ps)); [print(x.title,'|',x.price,'|',x.url) for x in list(ps)[:3]]"
```
Expected: `postings: > 0`. Mismo procedimiento de arreglo si falla.

- [ ] **Step 3: Correr toda la suite**

Run: `python -m pytest tests/ -v`
Expected: todo PASA.

- [ ] **Step 4: Commit (solo si hubo cambios)**

```bash
git add scraper_app/parsers/zonaprop.py scraper_app/parsers/argenprop.py
git commit -m "fix: update Zonaprop/Argenprop selectors after live verification

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: End-to-end al grupo de Telegram

> **GATE:** necesita `bot_token` + `chat_room` reales en `config.yaml`, y al menos una `*_full_url` válida.

**Files:**
- (ninguno; corrida de verificación)

- [ ] **Step 1: Armar config.yaml real**

Copiar `config.example.yaml` a `config.yaml` (gitignored — confirmar que `.gitignore` lo excluye; si no, agregarlo) y completar `bot_token`, `chat_room`, `persist: false` y al menos una URL.

- [ ] **Step 2: Corrida única**

Run: `python main.py config.yaml`
Expected: logs de scrap por sitio, "Postings saved", y mensajes en el grupo de Telegram nuevo.

- [ ] **Step 3: Verificar dedup**

Run de nuevo: `python main.py config.yaml`
Expected: "About to send 0 postings" (o muy pocos) — confirma que el dedup por `sha` funciona.

- [ ] **Step 4: (si `config.yaml` no estaba en `.gitignore`) commitear el ignore**

```bash
git add .gitignore
git commit -m "chore: ignore config.yaml (contiene secretos)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review (cobertura del spec)

- Remax vía API JSON (gateway + parser + factory + config) → Tasks 2–6. ✔
- Paginación 0-indexed de Remax → Task 1. ✔
- Filtrado solo por URL (sin capa de filtros) → diseño; nada de filtros en código. ✔
- Mismo bot/grupo de mudarme-bot → Tasks 6, 9. ✔
- Verificar/arreglar Zonaprop/Argenprop (stale) → Task 8. ✔
- Tests del parser + fixture; smoke en vivo; e2e → Tasks 3, 7, 8, 9. ✔
- Endpoint de Remax desconocido (gate por input del usuario) → Task 7. ✔
- Riesgo anti-bot 403 → checks explícitos en Tasks 7 y 8 con criterio de reporte. ✔
