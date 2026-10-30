from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Optional, Set

from .base import BaseParser
from .rsc import clean_str, parse_iso_date, rsc_array
from posting_app.database import Posting
from scraper_app.filters import AndFilter, ListingFilter
from scraper_app.publication import relative_label


@dataclass(frozen=True)
class Century21Listing:
    '''Vista limpia de un aviso de Century 21 (cumple el Listing de filters.py).

    `from_api` es el unico lugar que conoce el schema crudo del sitio.
    '''

    id: str
    titulo: str
    tipo: Optional[str]
    estado_reserva: Optional[str]
    precio: Optional[float]
    moneda: Optional[str]
    precio_oculto: bool
    antiguedad_anos: Optional[int]
    ambientes: Optional[int]
    dormitorios: Optional[int]
    superficie_cubierta: Optional[float]
    barrio: Optional[str]
    direccion: Optional[str]
    fecha_creacion: Optional[datetime]
    publicado: bool = True
    bloqueado: bool = False
    eliminado: bool = False

    # "reserved" y "under_offer" (oferta aceptada) ya no estan disponibles.
    _NO_DISPONIBLE = {'reserved': 'reservado', 'under_offer': 'reservado'}

    @classmethod
    def from_api(cls, raw: Dict[str, Any], today: Optional[date] = None) -> 'Century21Listing':
        year = _as_int(raw.get('construction_year'))
        current_year = (today or date.today()).year
        street = ' '.join(filter(None, [clean_str(raw.get('addr_street')),
                                        clean_str(str(raw.get('addr_number') or ''))]))
        return cls(
            id=str(raw['property_id']),
            titulo=clean_str(raw.get('title')) or '',
            tipo=clean_str(raw.get('prop_type')),
            estado_reserva=cls._NO_DISPONIBLE.get(raw.get('status')),
            precio=_as_float(raw.get('price')),
            moneda=clean_str(raw.get('currency_id')),
            precio_oculto=bool(raw.get('price_hidden')),
            # Sin año (o 0) = dato faltante: el filtro de antiguedad lo deja pasar.
            antiguedad_anos=max(current_year - year, 0) if year else None,
            ambientes=_as_int(raw.get('rooms')),
            dormitorios=_as_int(raw.get('bedrooms')),
            superficie_cubierta=_as_float(raw.get('covered_square_meters')),
            barrio=clean_str(raw.get('addr_subarea')) or clean_str(raw.get('addr_district')),
            direccion=street or None,
            fecha_creacion=parse_iso_date(raw.get('created_at')),
        )


class Century21Parser(BaseParser):
    '''century21.com.ar es Next.js: el listado viene en el payload RSC como
    `initialProperties`. La URL filtra barrio, precio, ambientes, m2 y apto
    credito; antiguedad y reservas se filtran aca (el sitio no lo permite).
    '''

    _base_url = 'https://www.century21.com.ar'

    def __init__(self, listing_filter: Optional[ListingFilter] = None):
        self._filter = listing_filter or AndFilter([])

    def get_soup_object(self, html: str):
        self._raw = html or ''

    def extract_data(self) -> Set[Posting]:
        self.page_keys = set()
        postings: Set[Posting] = set()

        for raw in rsc_array(self._raw, 'initialProperties'):
            try:
                listing = Century21Listing.from_api(raw)
            except (KeyError, TypeError, ValueError):
                continue

            href = '{}/propiedades/{}'.format(self._base_url, listing.id)
            # Todos los de la pagina, antes de filtrar: si no, una pagina sin
            # matches cortaria la paginacion antes de tiempo.
            self.page_keys.add(href)
            if not self._filter.matches(listing):
                continue

            postings.add(Posting(
                sha=self.get_id(href),
                url=href,
                title=self.sanitize_text(listing.titulo or 'Propiedad en venta')[:100],
                price=_format_price(listing),
                location=' · '.join(filter(None, [listing.barrio, listing.direccion])),
                description=_describe(listing),
                published=relative_label(listing.fecha_creacion),
            ))

        return postings


def _format_price(listing: Century21Listing) -> str:
    if listing.precio_oculto or not listing.precio:
        return 'Consultar precio'
    return '{} {:,}'.format(listing.moneda or '', int(listing.precio)).strip()


def _describe(listing: Century21Listing) -> str:
    return ' | '.join(filter(None, [
        (listing.tipo or '').capitalize() or None,
        f'{listing.superficie_cubierta:.0f} m2 cub' if listing.superficie_cubierta else None,
        f'{listing.ambientes} amb' if listing.ambientes else None,
        f'{listing.dormitorios} dorm' if listing.dormitorios else None,
        f'{listing.antiguedad_anos} años' if listing.antiguedad_anos is not None else None,
        'Apto crédito',
    ]))


def _as_int(value: Any) -> Optional[int]:
    try:
        return None if value in (None, '') else int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        return None if value in (None, '') else float(value)
    except (TypeError, ValueError):
        return None
