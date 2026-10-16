'''Filtros locales componibles (patron Specification).

La mayoria de los sitios filtran por URL. BNA +Hogares no permite filtrar por
antiguedad, ambientes minimos ni superficie, asi que esos criterios se aplican
aca, despues de traer los datos. Cada filtro decide si un aviso pasa o no;
`AndFilter` los combina.

Politica ante dato faltante: si el aviso no informa el campo, PASA. Preferimos
avisar de mas antes que perder una publicacion valida que no cargo el dato.
'''

from abc import ABC, abstractmethod
from typing import Iterable, Mapping, Optional, Protocol


class Listing(Protocol):
    tipo: Optional[str]
    antiguedad_anos: Optional[int]
    ambientes: Optional[int]
    superficie_cubierta: Optional[float]
    estado_reserva: Optional[str]
    publicado: bool
    bloqueado: bool
    eliminado: bool


class ListingFilter(ABC):
    @abstractmethod
    def matches(self, listing: Listing) -> bool: ...


class AndFilter(ListingFilter):
    '''Combina N filtros con AND. Sin filtros, deja pasar todo.'''

    def __init__(self, filters: Iterable[ListingFilter]):
        self._filters = tuple(filters)

    def matches(self, listing: Listing) -> bool:
        return all(f.matches(listing) for f in self._filters)


class TiposPermitidosFilter(ListingFilter):
    def __init__(self, tipos: Iterable[str]):
        self._tipos = frozenset(_norm(t) for t in tipos)

    def matches(self, listing: Listing) -> bool:
        return listing.tipo is not None and _norm(listing.tipo) in self._tipos


class MaxAntiguedadFilter(ListingFilter):
    '''Antiguedad maxima, con override opcional por tipo (ej: PH hasta 20).'''

    def __init__(self, max_anos: int, por_tipo: Optional[Mapping[str, int]] = None):
        self._max = max_anos
        self._por_tipo = {_norm(k): v for k, v in (por_tipo or {}).items()}

    def matches(self, listing: Listing) -> bool:
        if listing.antiguedad_anos is None:
            return True
        limite = self._por_tipo.get(_norm(listing.tipo or ''), self._max)
        return listing.antiguedad_anos <= limite


class MinAmbientesFilter(ListingFilter):
    def __init__(self, min_ambientes: int):
        self._min = min_ambientes

    def matches(self, listing: Listing) -> bool:
        return listing.ambientes is None or listing.ambientes >= self._min


class MinSuperficieCubiertaFilter(ListingFilter):
    def __init__(self, min_m2: float):
        self._min = min_m2

    def matches(self, listing: Listing) -> bool:
        return listing.superficie_cubierta is None or listing.superficie_cubierta >= self._min


class ExcluirReservadasFilter(ListingFilter):
    _RESERVADOS = frozenset({'reservado', 'reservada'})

    def matches(self, listing: Listing) -> bool:
        return _norm(listing.estado_reserva or '') not in self._RESERVADOS


class PublicadaValidaFilter(ListingFilter):
    '''Excluye avisos no publicados, bloqueados o eliminados.'''

    def matches(self, listing: Listing) -> bool:
        return listing.publicado and not listing.bloqueado and not listing.eliminado


def _norm(s: str) -> str:
    return s.strip().lower()
