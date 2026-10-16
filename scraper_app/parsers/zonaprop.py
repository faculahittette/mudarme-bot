from typing import Set

from bs4 import BeautifulSoup

from .base import BaseParser
from posting_app.database import Posting, PostingRepository


class ZonapropParser(BaseParser):
    # Zonaprop usa atributos data-qa estables (mas robustos que las clases
    # CSS-module hasheadas, que cambian de sufijo entre releases).
    base_info_selector = 'div[data-qa="posting PROPERTY"]'
    link_regex = '[data-qa="POSTING_CARD_DESCRIPTION"] a'
    price_regex = '[data-qa="POSTING_CARD_PRICE"]'
    description_regex = '[data-qa="POSTING_CARD_DESCRIPTION"]'
    location_regex = '[data-qa="POSTING_CARD_LOCATION"]'
    features_regex = '[data-qa="POSTING_CARD_FEATURES"] span'
    _base_url = 'https://www.zonaprop.com.ar'

    @staticmethod
    def _title_from_url(href: str) -> str:
        '''`.../clasificado/veclapin-venta-depto-3-amb-en-caballito-60369197.html`
        -> `Venta depto 3 amb en caballito`.'''
        slug = href.rstrip('/').rsplit('/', 1)[-1].rsplit('.', 1)[0]
        words = [w for w in slug.split('-') if w]
        if words and words[0].isalpha() and len(words[0]) == 8 and words[0].startswith('vec'):
            words = words[1:]  # prefijo de tipo de aviso (`veclapin`, `veclcain`...)
        if words and words[-1].isdigit():
            words = words[:-1]  # id del aviso
        return ' '.join(words).capitalize()[:100]

    def _excerpt(self, link_container) -> str:
        raw = link_container.get_text(separator=' ').strip()
        if 'Descripción' in raw:
            raw = raw.split('Descripción')[0]
        return self.sanitize_text(raw)[:100]

    def extract_data(self) -> Set[Posting]:
        '''Extracting data and returning list of postings'''
        postings = set()
        self.page_keys = set()
        base_info_soaps = self.soup.select(self.base_info_selector)

        for base_info_soap in base_info_soaps:
            link_container = base_info_soap.select_one(self.link_regex)
            price_container = base_info_soap.select_one(self.price_regex)
            description_container = base_info_soap.select_one(self.description_regex)
            location_container = base_info_soap.select_one(self.location_regex)

            if not (link_container and description_container and location_container):
                # price may be 'Consultar precio' or missing, but link/description/location are required
                continue

            # Sin query string: trae parametros de tracking (n_search_id...)
            # que cambian en cada request.
            href = '{}{}'.format(
                self._base_url,
                link_container.get('href', '').split('?')[0],
            )

            # El texto del link es un extracto de la descripcion (a veces vacio,
            # ej: emprendimientos). El titulo real del aviso viaja en el slug.
            title = self._title_from_url(href) or self._excerpt(link_container)

            self.page_keys.add(href)
            sha = self.get_id(href)
            price = self.sanitize_text(price_container.get_text()) if price_container else ''

            # Build brief description from features (m2, ambs) if present
            features = [self.sanitize_text(f.get_text()) for f in base_info_soap.select(self.features_regex)]
            if features:
                description = ' | '.join(features)
            else:
                # fallback: short excerpt of the long description
                description = self.sanitize_text(description_container.get_text())[:140]

            location = self.sanitize_text(location_container.get_text())

            posting_repository = PostingRepository()
            if posting_repository.get_posting_by_sha(sha):
                continue

            new_posting = Posting(
                sha=sha,
                url=href,
                title=title,
                price=price,
                description=description,
                location=location,
            )
            postings.add(new_posting)

        return postings
