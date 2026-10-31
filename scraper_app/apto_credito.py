'''Apto credito segun el texto del aviso (titulo, descripcion, caracteristicas).

Para avisos que NO tienen tildada la marca "apto credito" del sitio pero que
lo dicen en el texto. Es conservador a proposito: ante una negacion o una duda
devuelve NO / DESCONOCIDO, porque un falso positivo es spam en Telegram.
'''

import re
from enum import Enum
from typing import Dict, Tuple

from bs4 import BeautifulSoup


class Veredicto(str, Enum):
    SI = 'si'
    NO = 'no'
    DESCONOCIDO = 'desconocido'


_CREDITO = r'(?:a\s+|para\s+)?cr[eé]d'

# "No es apto credito", "NO apto credito", "no acepta credito",
# "Apto credito: No", "¿Es apto credito? No", "sin apto credito".
_NO = re.compile(
    r'\bno\s+(?:es\s+)?apto\s*' + _CREDITO
    + r'|\bno\s+acepta\s+cr[eé]d'
    + r'|\bapto\s*' + _CREDITO + r'[a-zé]*\s*[:?]?\s*no\b'
    + r'|\bsin\s+apto\s*' + _CREDITO,
    re.IGNORECASE,
)
# "Apto credito a consultar", "consultar si es apto credito", "en tramite".
_DUDA = re.compile(
    r'\bapto\s*' + _CREDITO + r'[a-zé]*\s*[:\-]?\s*(?:a\s+)?(?:consultar|confirmar|verificar|en\s+tr[aá]mite)'
    + r'|\b(?:consultar|verificar)\s+(?:si\s+)?(?:es\s+)?apto\s*' + _CREDITO,
    re.IGNORECASE,
)
_SI = re.compile(r'\bapto\s*' + _CREDITO, re.IGNORECASE)


def clasificar(texto: str) -> Veredicto:
    '''SI solo si el texto dice apto credito sin negarlo ni dejarlo en duda.'''
    texto = ' '.join((texto or '').split())
    if _NO.search(texto):
        return Veredicto.NO
    if _DUDA.search(texto):
        return Veredicto.DESCONOCIDO
    if _SI.search(texto):
        return Veredicto.SI
    return Veredicto.DESCONOCIDO


# Partes de la pagina del aviso que hablan de ESA propiedad (nada de avisos
# similares, menus ni filtros, que tambien dicen "apto credito").
SELECTORES: Dict[str, Tuple[str, ...]] = {
    'zonaprop': ('h1', '#reactDescription'),
    'argenprop': ('h1', '.section-description--content', 'ul.property-features'),
    'mercadolibre': ('h1', '.ui-pdp-description__content', 'tr'),
}


def texto_del_aviso(site: str, html: str) -> str:
    soup = BeautifulSoup(html or '', 'html.parser')
    partes = [
        el.get_text(' ')
        for selector in SELECTORES[site]
        for el in soup.select(selector)
    ]
    return ' '.join(' '.join(partes).split())


def veredicto_del_aviso(site: str, html: str) -> Veredicto:
    return clasificar(texto_del_aviso(site, html))
