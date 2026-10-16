import json
import re
from typing import Any, Dict, List, Optional, Set

from .base import BaseParser
from posting_app.database import Posting, PostingRepository


class RoomixParser(BaseParser):
    '''Roomix es una app Next.js: el listado llega dentro del payload RSC
    (`self.__next_f.push([1, "..."])`) como un array `initialResults` con
    objetos JSON limpios (slug, precio, ambientes, m2...). Lo leemos de ahi en
    vez de scrapear el HTML renderizado, que usa clases de Tailwind inestables.
    '''

    _base_url = 'https://roomix.ai'
    _RSC_CHUNK = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')
    _MARKER = '"initialResults":'

    def get_soup_object(self, html: str):
        self._raw = html or ''

    def extract_data(self) -> Set[Posting]:
        self.page_keys = set()
        postings: Set[Posting] = set()
        posting_repository = PostingRepository()

        for item in self._initial_results():
            slug = _clean(item.get('slug'))
            if not slug:
                continue
            href = '{}/propiedad/{}'.format(self._base_url, slug)
            self.page_keys.add(href)

            sha = self.get_id(href)
            if posting_repository.get_posting_by_sha(sha):
                continue

            postings.add(Posting(
                sha=sha,
                url=href,
                title=self.sanitize_text(_clean(item.get('title')) or slug)[:100],
                price=_format_price(item),
                location=_clean(item.get('location_address')) or _clean(item.get('location_city')) or '',
                description=_describe(item),
            ))

        return postings

    def _initial_results(self) -> List[Dict[str, Any]]:
        rsc = ''.join(self._decode_chunks())
        start = rsc.find(self._MARKER)
        if start < 0:
            return []
        try:
            results, _ = json.JSONDecoder().raw_decode(rsc, start + len(self._MARKER))
        except ValueError:
            return []
        return [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []

    def _decode_chunks(self):
        for match in self._RSC_CHUNK.finditer(self._raw):
            try:
                yield json.loads(match.group(1))
            except ValueError:
                continue


def _clean(value: Any) -> Optional[str]:
    '''Los strings que empiezan con `$` son referencias internas de RSC.'''
    if not isinstance(value, str) or value.startswith('$'):
        return None
    return value.strip() or None


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
