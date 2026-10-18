from abc import ABC
from typing import Callable, List, Tuple

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


CLOUDSCRAPER: Client = ('cloudscraper', cloudscraper.create_scraper)
PLAIN: Client = ('requests', _plain_session)


class BaseGateway(ABC):
    paginated = True
    first_page = 1
    timeout_seconds = 30
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
            if res.ok:
                if not quiet:
                    console.log(f'{self._name} responded OK!', style='green')
                return res.text
            console.log(
                f'[bold u]ERROR[/bold u]: {self._name} ({client_name}) responded'
                f' with error [red bold]{res.status_code}[/red bold]!',
                style='red'
            )
        return ''
