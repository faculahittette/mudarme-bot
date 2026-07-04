from abc import ABC

import cloudscraper
from requests.exceptions import InvalidSchema
from rich.console import Console

console = Console()


class BaseGateway(ABC):
    paginated = True
    first_page = 1

    def page_param(self, page: int) -> int:
        '''
        Transforma el indice de pagina al valor que va literalmente en la URL.

        Por defecto es identidad: Zonaprop usa el numero de pagina tal cual
        (`-pagina-2.html`) y Remax lo usa 0-indexed via `first_page`. Sitios
        que paginan por offset de item (ej: Mercado Libre con `_Desde_49`)
        sobreescriben este metodo.
        '''
        return page

    def make_request(self, url: str) -> str:
        '''
        Makes the request to the full_url using cloudscraper
        and returns the html in it.
        '''
        html = ''
        scraper = cloudscraper.create_scraper()
        console.log(
            'On my way to [bold cyan]GET[/bold cyan] [u]{}[/u]'.format(
                self._name
            )
        )

        try:
            res = scraper.get(url)
        except InvalidSchema as e:
            console.log(
                '[bold u]ERROR[/bold u]: {} raised InvalidSchema.\n {}'.format(
                     self._name, e
                )
            )

        if res.ok:
            html = res.text
            console.log(
                '{} responded OK!'.format(self._name),
                style='green'
            )
        else:
            console.log(
                (
                    '[bold u]ERROR[/bold u]: {} responded'
                    ' with error [red bold]{}[/red bold]!'.format(
                        self._name, res.status_code
                    )
                ),
                style='red'
            )

        return html