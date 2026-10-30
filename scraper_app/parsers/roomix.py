from typing import Any, Dict, Set

from .base import BaseParser
from .rsc import clean_str as _clean, parse_iso_date, rsc_array
from scraper_app.publication import relative_label
from posting_app.database import Posting


class RoomixParser(BaseParser):
    '''Roomix es una app Next.js: el listado llega dentro del payload RSC
    (`self.__next_f.push([1, "..."])`) como un array `initialResults` con
    objetos JSON limpios (slug, precio, ambientes, m2...). Lo leemos de ahi en
    vez de scrapear el HTML renderizado, que usa clases de Tailwind inestables.
    '''

    _base_url = 'https://roomix.ai'

    def get_soup_object(self, html: str):
        self._raw = html or ''

    def extract_data(self) -> Set[Posting]:
        self.page_keys = set()
        postings: Set[Posting] = set()

        for item in rsc_array(self._raw, 'initialResults'):
            slug = _clean(item.get('slug'))
            if not slug:
                continue
            href = '{}/propiedad/{}'.format(self._base_url, slug)
            self.page_keys.add(href)

            sha = self.get_id(href)
            postings.add(Posting(
                sha=sha,
                url=href,
                title=self.sanitize_text(_clean(item.get('title')) or slug)[:100],
                price=_format_price(item),
                location=_clean(item.get('location_address')) or _clean(item.get('location_city')) or '',
                description=_describe(item),
                published=relative_label(parse_iso_date(item.get('publication_date'))),
            ))

        return postings


def _format_price(item: Dict[str, Any]) -> str:
    price = item.get('price')
    if not isinstance(price, (int, float)) or not price:
        return 'Consultar precio'
    return '{} {:,}'.format(_clean(item.get('currency')) or '', int(price)).strip()


def _describe(item: Dict[str, Any]) -> str:
    parts = [
        _clean(item.get('property_type')),
        '{} m2 cub'.format(item['covered_area_m2']) if item.get('covered_area_m2') else None,
        '{} amb'.format(item['rooms']) if item.get('rooms') else None,
        '{} dorm'.format(item['bedrooms']) if item.get('bedrooms') else None,
    ]
    return ' | '.join(p for p in parts if p)
