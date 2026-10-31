'''Avisos SIN la marca "apto credito" del sitio que lo dicen en su texto.

Corre sobre busquedas iguales a las normales pero sin el filtro de apto
credito. Solo entra a la pagina de los avisos que nunca vio (ni como aviso
guardado ni como ya revisado) y guarda para enviar unicamente los que dicen
apto credito sin negarlo.
'''

from collections import Counter
from typing import Optional

from rich.console import Console

from .database import AptoCreditoCheckRepository, PostingRepository
from scraper_app.apto_credito import Veredicto, clasificar, texto_del_aviso
from scraper_app.parsers import BaseParser
from scraper_app.publication import label_from_html
from scraper_app.services import ScraperService, ScraperServiceFactory

console = Console()

BADGE = '\U0001F50E Apto crédito según la descripción (el aviso no tiene la marca)'


class AptoCreditoPorDescripcionService:
    def __init__(
        self,
        site: str,
        scraper_service: ScraperService,
        postings: Optional[PostingRepository] = None,
        checks: Optional[AptoCreditoCheckRepository] = None,
    ):
        self._site = site
        self._scraper = scraper_service
        self._postings = postings or PostingRepository()
        self._checks = checks or AptoCreditoCheckRepository()

    def scrap_and_create_postings(self) -> bool:
        '''Misma interfaz que PostingService: False si la busqueda quedo incompleta.'''
        postings = self._scraper.get_postings_from_scraper()
        shas = [p.sha for p in postings]
        known = set(self._postings.get_postings_by_sha(shas)) | self._checks.checked_shas(shas)
        pending = [p for p in postings if p.sha not in known]
        console.log(f'Apto credito por descripcion: {len(pending)} avisos sin revisar')

        resultados = Counter()
        for posting in pending:
            html = self._scraper.fetch_detail(posting.url)
            if html is None:
                resultados['sin respuesta'] += 1  # se reintenta en otra corrida
                continue
            texto = texto_del_aviso(self._site, html)
            if not texto:
                # Pagina sin titulo ni descripcion: anti-robots o el sitio
                # cambio su HTML. No se marca como revisado: se reintenta.
                resultados['sin texto'] += 1
                continue
            veredicto = clasificar(texto)
            resultados[veredicto.value] += 1
            if veredicto is Veredicto.SI:
                self._save_for_sending(posting, html)
            self._checks.save(posting.sha, posting.url, veredicto.value)

        if pending:
            console.log(f'Resultado: {dict(resultados)}')
        return self._scraper.complete

    def _save_for_sending(self, posting, html: str) -> None:
        posting.badge = BADGE
        if self._scraper.publication_in_detail_page:
            posting.published = label_from_html(html)
        self._postings.create_posting(posting)


class AptoCreditoServiceFactory:
    @classmethod
    def build(
        cls,
        site: str,
        pages: int,
        full_url: str,
        parser: Optional[BaseParser] = None,
    ) -> AptoCreditoPorDescripcionService:
        scraper = ScraperServiceFactory.build(site=site, pages=pages, full_url=full_url, parser=parser)
        return AptoCreditoPorDescripcionService(site=site, scraper_service=scraper)
