import time
from abc import ABC
from typing import Callable, List, Optional, Tuple

import cloudscraper
import requests
from rich.console import Console

console = Console()

# Un "cliente" es (nombre, fabrica de sesion). Cada gateway declara cuales
# probar y en que orden; el primero que responde OK gana.
Client = Tuple[str, Callable[[], requests.Session]]

_BROWSER_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/141.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-AR,es;q=0.9,en;q=0.8',
}


def _plain_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(_BROWSER_HEADERS)
    return session


class SourceUnavailable(Exception):
    '''El sitio no respondio OK en ninguno de los intentos (caido, timeout,
    anti-bot). Distinto de "no hay mas resultados": quien llama decide si
    la busqueda quedo incompleta.'''


CLOUDSCRAPER: Client = ('cloudscraper', cloudscraper.create_scraper)
PLAIN: Client = ('requests', _plain_session)


class BaseGateway(ABC):
    paginated = True
    first_page = 1
    timeout_seconds = 30
    #: Intentos por URL. Un timeout o un 5xx suelen ser pasajeros; sin
    #: reintento, la pagina vacia se toma como "fin de resultados" y se
    #: pierden las paginas siguientes.
    attempts = 2
    #: Espera antes del primer reintento; se duplica en cada intento siguiente
    #: (backoff exponencial: 5s, 10s, 20s...).
    retry_wait_seconds = 5
    #: Avisos por pagina cuando el sitio los fija (ej. `limit=48` en la API).
    #: Si una pagina trae menos, era la ultima y no se pide la siguiente.
    #: None = no se sabe (Zonaprop varia) y se corta solo por avisos repetidos.
    page_size: Optional[int] = None
    clients: List[Client] = [CLOUDSCRAPER]

    def page_param(self, page: int) -> int:
        '''
        Transforma el indice de pagina al valor que va literalmente en la URL.

        Por defecto es identidad: Zonaprop usa el numero de pagina tal cual
        (`-pagina-2.html`) y Remax lo usa 0-indexed via `first_page`. Sitios
        que paginan por offset de item (ej: Mercado Libre con `_Desde_49`)
        sobreescriben este metodo.
        '''
        return page

    # True si la pagina de cada aviso dice "Publicado hace X" (ver ScraperService).
    publication_in_detail_page = False

    def make_request(self, url: str, quiet: bool = False) -> str:
        '''GET con reintentos y backoff. Lanza SourceUnavailable si fallan todos.'''
        for attempt in range(1, self.attempts + 1):
            html = self._request_once(url, quiet)
            if html:
                return html
            if attempt < self.attempts:
                wait = self.retry_wait_seconds * 2 ** (attempt - 1)
                console.log(f'Reintentando {self._name} en {wait}s...', style='yellow')
                time.sleep(wait)
        console.log(
            f'[bold u]ATENCION[/bold u]: {self._name} no respondio; '
            'los resultados de esta busqueda pueden estar incompletos.',
            style='red bold'
        )
        raise SourceUnavailable(f'{self._name} no respondio ({url})')

    def _request_once(self, url: str, quiet: bool) -> str:
        '''GET con el primer cliente que responda OK. Devuelve '' si ninguno.'''
        if not quiet:
            console.log(
                'On my way to [bold cyan]GET[/bold cyan] [u]{}[/u]'.format(self._name)
            )
        for client_name, make_session in self.clients:
            try:
                res = make_session().get(url, timeout=self.timeout_seconds)
            except Exception as e:  # noqa: BLE001 - red/anti-bot: logueamos y seguimos
                console.log(
                    f'[bold u]ERROR[/bold u]: {self._name} ({client_name}) fallo el request: {e}',
                    style='red'
                )
                continue
            # Solo 200: Argenprop, por ejemplo, responde 202 con una pantalla
            # anti-robots ("JavaScript is disabled") que parece una pagina vacia.
            if res.status_code == 200:
                if not quiet:
                    console.log(f'{self._name} responded OK!', style='green')
                return res.text
            console.log(
                f'[bold u]ERROR[/bold u]: {self._name} ({client_name}) responded'
                f' with error [red bold]{res.status_code}[/red bold]!',
                style='red'
            )
        return ''
