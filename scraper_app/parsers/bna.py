import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

from .base import BaseParser
from posting_app.database import Posting, PostingRepository
from scraper_app.filters import AndFilter, ListingFilter


@dataclass(frozen=True)
class BnaListing:
    '''Vista limpia de un aviso de la API de BNA +Hogares.

    `from_api` es el unico lugar que conoce el schema crudo: si la API cambia
    un nombre de campo, se toca solo aca.
    '''

    id: int
    titulo: str
    tipo: Optional[str]
    estado_propiedad: Optional[str]
    estado_reserva: Optional[str]
    precio: Optional[float]
    moneda: Optional[str]
    antiguedad_anos: Optional[int]
    ambientes: Optional[int]
    superficie_cubierta: Optional[float]
    localidad: Optional[str]
    direccion: Optional[str]
    publicado: bool
    bloqueado: bool
    eliminado: bool

    @classmethod
    def from_api(cls, raw: Dict[str, Any]) -> 'BnaListing':
        return cls(
            id=int(raw['id']),
            titulo=str(raw.get('titulo') or '').strip(),
            tipo=raw.get('tipo'),
            estado_propiedad=raw.get('estadoPropiedad'),
            estado_reserva=raw.get('estadoReserva'),
            precio=_as_float(raw.get('precio')),
            moneda=raw.get('moneda'),
            antiguedad_anos=_as_int(raw.get('antiguedadAnos')),
            ambientes=_as_int(raw.get('ambientes')),
            superficie_cubierta=_as_float(raw.get('superficieCubierta')),
            localidad=raw.get('localidad'),
            direccion=raw.get('direccionDescripcion'),
            publicado=bool(raw.get('publicado', False)),
            bloqueado=bool(raw.get('bloqueado', False)),
            eliminado=bool(raw.get('eliminado', False)),
        )


class BnaParser(BaseParser):
    '''Parsea la respuesta JSON de /api/propiedades y aplica filtros locales.

    El filtro se inyecta (DI) para que el parser no conozca la configuracion.
    '''

    _base_url = 'https://mashogaresconbna.com.ar'

    def __init__(self, listing_filter: Optional[ListingFilter] = None):
        self._filter = listing_filter or AndFilter([])

    def get_soup_object(self, html: str):
        '''La respuesta es JSON, no HTML: guardamos el texto crudo.'''
        self._raw = html

    def extract_data(self) -> Set[Posting]:
        self.page_keys = set()
        postings: Set[Posting] = set()
        posting_repository = PostingRepository()

        for raw in self._iter_raw_items():
            try:
                listing = BnaListing.from_api(raw)
            except (KeyError, TypeError, ValueError):
                continue

            href = '{}/propiedad/{}'.format(self._base_url, listing.id)
            self.page_keys.add(href)

            if not self._filter.matches(listing):
                continue

            sha = self.get_id(href)
            if posting_repository.get_posting_by_sha(sha):
                continue

            postings.add(Posting(
                sha=sha,
                url=href,
                title=self.sanitize_text(listing.titulo or 'Sin titulo')[:100],
                price=_format_price(listing.precio, listing.moneda),
                location=_join([listing.localidad, listing.direccion], ' · '),
                description=_describe(listing),
            ))

        return postings

    def _iter_raw_items(self) -> List[Dict[str, Any]]:
        try:
            payload = json.loads(getattr(self, '_raw', '') or '{}')
        except (TypeError, ValueError):
            return []
        # Sin resultados la API responde `internalStatus: NO_CONTENT` y no
        # trae la clave `response`.
        response = payload.get('response') if isinstance(payload, dict) else None
        data = (response or {}).get('data') or []
        return [item for item in data if isinstance(item, dict)]


def _describe(listing: BnaListing) -> str:
    return _join([
        listing.tipo,
        f'{listing.superficie_cubierta:.0f} m2 cub' if listing.superficie_cubierta else None,
        f'{listing.ambientes} amb' if listing.ambientes else None,
        f'{listing.antiguedad_anos} años' if listing.antiguedad_anos is not None else None,
        listing.estado_propiedad,
        'Apto crédito BNA',
    ], ' | ')


def _format_price(precio: Optional[float], moneda: Optional[str]) -> str:
    if not precio:
        return 'Consultar precio'
    return '{} {:,}'.format(moneda or '', int(precio)).strip()


def _join(parts: Iterable[Optional[str]], sep: str) -> str:
    return sep.join(p for p in parts if p)


def _as_int(value: Any) -> Optional[int]:
    try:
        return None if value in (None, '') else int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        return None if value in (None, '') else float(value)
    except (TypeError, ValueError):
        return None
