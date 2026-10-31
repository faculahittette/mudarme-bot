from typing import List, Optional

from rich.console import Console

from .database import Posting, PostingRepository
from .prices import parse_price, price_drop
from scraper_app.parsers import BaseParser
from scraper_app.services import ScraperService, ScraperServiceFactory

console = Console()


class PostingService:
    '''Toma lo que trae el scraper y decide que hacer con cada aviso:

    - nuevo        -> se guarda (y el envio normal lo manda a Telegram).
    - ya conocido  -> si bajo de precio, queda pendiente como "Bajo de precio";
                      si subio, solo se actualiza el precio guardado.
    '''

    def __init__(
        self,
        scraper_service: ScraperService,
        repository: Optional[PostingRepository] = None,
    ):
        self._scraper_service = scraper_service
        self._repository = repository or PostingRepository()

    def scrap_and_create_postings(self) -> bool:
        '''Devuelve False si el sitio no respondio y la busqueda quedo incompleta.'''
        postings = self._scraper_service.get_postings_from_scraper()
        known = self._repository.get_postings_by_sha(p.sha for p in postings)

        new = [p for p in postings if p.sha not in known]
        seen = [(known[p.sha], p) for p in postings if p.sha in known]

        # Precios antes de guardar: al guardar, SQLAlchemy "expira" los
        # objetos nuevos y no se pueden volver a leer fuera de la sesion.
        drops = sum(self._track_price(stored, scraped) for stored, scraped in seen)
        if drops:
            console.log(f'{drops} avisos bajaron de precio', style='green')

        self._save_new(new)
        return self._scraper_service.complete

    def _save_new(self, postings: List[Posting]) -> None:
        self._scraper_service.add_publication_dates(postings)
        console.log(f'About to save {len(postings)} new postings')
        saved = sum(self._repository.create_posting(p) for p in postings)
        if saved < len(postings):
            console.log(f'{len(postings) - saved} ya estaban en la base (los guardo otra compu)')
        console.log('Postings saved successfully!', style='green')

    def _track_price(self, stored: Posting, scraped: Posting) -> bool:
        '''Devuelve True si registro una baja de precio para avisar.'''
        # Sin monto ("Consultar precio") no pisamos el precio que ya teniamos.
        if scraped.price == stored.price or parse_price(scraped.price) is None:
            return False
        is_drop = price_drop(stored.price, scraped.price) is not None
        updated = self._repository.update_price(
            stored.sha, stored.price, scraped.price, notify_drop=is_drop
        )
        return is_drop and updated


class PostingServiceFactory:
    @classmethod
    def build(
        cls,
        site: str,
        pages: int,
        full_url: str,
        parser: Optional[BaseParser] = None,
    ) -> PostingService:
        scraper_service = ScraperServiceFactory.build(
            site=site,
            pages=pages,
            full_url=full_url,
            parser=parser,
        )
        return PostingService(scraper_service=scraper_service)
