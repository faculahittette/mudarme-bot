from typing import Dict, Optional, Set, Tuple, Type

from rich.console import Console

from .gateways import (
    ArgenpropGateway,
    BaseGateway,
    BnaGateway,
    LaVozGateway,
    MercadolibreGateway,
    ProperatiGateway,
    RemaxGateway,
    RoomixGateway,
    ZonapropGateway,
)
from .parsers import (
    ArgenpropParser,
    BaseParser,
    BnaParser,
    LaVozParser,
    MercadolibreParser,
    ProperatiParser,
    RemaxParser,
    RoomixParser,
    ZonapropParser,
)
from posting_app.database import Posting
from .publication import label_from_html

console = Console()


class ScraperService:
    def __init__(
        self,
        pages: int,
        url: str,
        gateway: BaseGateway,
        parser: BaseParser,
    ):
        self._pages = pages
        self._url = url
        self._gateway = gateway
        self._parser = parser

    def get_postings_from_scraper(self) -> Set[Posting]:
        postings = set()
        pages = self._pages if self._gateway.paginated else 1
        first_page = getattr(self._gateway, 'first_page', 1)
        # Avisos vistos en esta corrida (antes de filtrar/deduplicar). Sirve
        # para cortar apenas se agotan los resultados en vez de pedir siempre
        # `pages` paginas: Zonaprop, por ejemplo, devuelve la pagina 1 cuando
        # pedis una pagina fuera de rango.
        seen_keys: Set[str] = set()

        for page in range(first_page, first_page + pages):
            console.log(f'Page {page} of {pages}')
            # Algunos sitios (ej: Mercado Libre) paginan por offset de item, no
            # por numero de pagina. El gateway traduce el indice al valor real.
            page_param = getattr(self._gateway, 'page_param', lambda p: p)(page)
            html = self._gateway.make_request(
                url=self._url.format(page_param)
            )

            self._parser.get_soup_object(html=html)
            new_postings = self._parser.extract_data()
            console.log(f'Got {len(new_postings)} new postings')

            postings = postings.union(new_postings)

            page_keys = getattr(self._parser, 'page_keys', None)
            if page_keys is not None:
                if not page_keys - seen_keys:
                    console.log('No hay avisos nuevos en esta pagina: fin de resultados')
                    break
                seen_keys |= page_keys

        self._add_publication_dates(postings)
        return postings

    def _add_publication_dates(self, postings: Set[Posting]) -> None:
        '''Para sitios que solo muestran la antiguedad en la pagina del aviso
        (Zonaprop, Mercado Libre): una visita extra por aviso NUEVO.'''
        if not getattr(self._gateway, 'publication_in_detail_page', False):
            return
        pending = [p for p in postings if not p.published]
        if pending:
            console.log(f'Buscando fecha de publicacion de {len(pending)} avisos nuevos')
        for posting in pending:
            html = self._gateway.make_request(url=posting.url, quiet=True)
            posting.published = label_from_html(html)


# Registro sitio -> (gateway, parser por defecto). Agregar un sitio nuevo es
# sumar una linea aca (Open/Closed): el resto del flujo no cambia.
SITES: Dict[str, Tuple[Type[BaseGateway], Type[BaseParser]]] = {
    'zonaprop': (ZonapropGateway, ZonapropParser),
    'argenprop': (ArgenpropGateway, ArgenpropParser),
    'mercadolibre': (MercadolibreGateway, MercadolibreParser),
    'la_voz': (LaVozGateway, LaVozParser),
    'properati': (ProperatiGateway, ProperatiParser),
    'remax': (RemaxGateway, RemaxParser),
    'roomix': (RoomixGateway, RoomixParser),
    'bna': (BnaGateway, BnaParser),
}


class ScraperServiceFactory:
    @classmethod
    def build(
        cls,
        site: str,
        pages: int,
        full_url: str,
        parser: Optional[BaseParser] = None,
    ) -> ScraperService:
        '''Arma el scraper de `site`. `parser` permite inyectar uno ya
        configurado (ej: BNA con sus filtros locales).'''
        gateway_cls, parser_cls = SITES[site]
        return ScraperService(
            pages=pages,
            url=full_url,
            gateway=gateway_cls(),
            parser=parser or parser_cls(),
        )
