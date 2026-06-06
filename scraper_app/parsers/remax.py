import json
from typing import Set

from .base import BaseParser
from posting_app.database import Posting, PostingRepository


class RemaxParser(BaseParser):
    _base_url = 'https://www.remax.com.ar'

    def get_soup_object(self, html: str):
        '''La respuesta de Remax es JSON, no HTML: guardamos el texto crudo.'''
        self._raw = html

    def _iter_listings(self, payload):
        '''Devuelve la lista de publicaciones tolerando variantes del contenedor.
        Ajustar contra la respuesta real (ver Task 7).'''
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            data = payload.get('data', payload)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get('data') or data.get('content') or data.get('results') or []
        return []

    def _format_price(self, item) -> str:
        # En la API de Remax el precio es un numero y la moneda viene aparte
        # en currency.value (ej: price=195000, currency={"value": "USD"}).
        amount = item.get('price')
        currency_obj = item.get('currency')
        currency = ''
        if isinstance(currency_obj, dict):
            currency = currency_obj.get('value') or ''
        if isinstance(amount, (int, float)) and amount:
            # La API manda el monto como float (195000.0); lo mostramos entero.
            return '{} {:,}'.format(currency, int(amount)).strip()
        return 'Consultar precio'

    def extract_data(self) -> Set[Posting]:
        postings = set()
        try:
            payload = json.loads(self._raw) if getattr(self, '_raw', '') else {}
        except (ValueError, TypeError):
            return postings

        posting_repository = PostingRepository()

        for item in self._iter_listings(payload):
            if not isinstance(item, dict):
                continue

            slug = item.get('slug') or ''
            listing_id = str(item.get('id') or '')
            if slug:
                href = '{}/listings/{}'.format(self._base_url, slug)
            elif listing_id:
                href = '{}/listings/{}'.format(self._base_url, listing_id)
            else:
                continue

            sha = self.get_id(href)
            if posting_repository.get_posting_by_sha(sha):
                continue

            title = self.sanitize_text(item.get('title') or '')[:100]
            price = self._format_price(item)
            # geoLabel trae el barrio ("Caballito, Capital Federal");
            # displayAddress es la calle ("Av. Gaona 1600").
            location = self.sanitize_text(item.get('geoLabel') or '')

            features = []
            if item.get('dimensionCovered'):
                features.append('{} m2'.format(item['dimensionCovered']))
            if item.get('totalRooms'):
                features.append('{} amb'.format(item['totalRooms']))
            if item.get('bedrooms'):
                features.append('{} dorm'.format(item['bedrooms']))
            description = ' | '.join(features)

            postings.add(Posting(
                sha=sha,
                url=href,
                title=title,
                price=price,
                description=description,
                location=location,
            ))

        return postings
