from typing import Optional

from rich.console import Console

from .database import PostingRepository
from scraper_app.parsers import BaseParser
from scraper_app.services import ScraperService, ScraperServiceFactory

console = Console()


class PostingService:
    def __init__(self, scraper_service: ScraperService):
        self._scraper_service = scraper_service

    def scrap_and_create_postings(self):
        postings = self._scraper_service.get_postings_from_scraper()
        posting_repository = PostingRepository()

        console.log(f'About to save {len(postings)} postings')
        saved = sum(posting_repository.create_posting(p) for p in postings)
        if saved < len(postings):
            console.log(f'{len(postings) - saved} ya estaban en la base (los guardo otra compu)')
        console.log('Postings saved successfully!', style='green')


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
