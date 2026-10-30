'''Lectura del payload RSC de sitios hechos con Next.js (App Router).

Estas paginas mandan los datos dentro de `self.__next_f.push([1, "..."])`, a
veces partidos en varios chunks. Leerlos de ahi es mas estable que scrapear el
HTML renderizado (clases de Tailwind que cambian con cada deploy).
Lo usan Roomix (`initialResults`) y Century 21 (`initialProperties`).
'''

import json
import re
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

_RSC_CHUNK = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')


def rsc_array(html: str, key: str) -> List[Dict[str, Any]]:
    '''Los objetos del primer array `"key": [...]` del payload ([] si no esta).'''
    rsc = ''.join(_decode_chunks(html or ''))
    marker = f'"{key}":'
    start = rsc.find(marker)
    if start < 0:
        return []
    try:
        results, _ = json.JSONDecoder().raw_decode(rsc, start + len(marker))
    except ValueError:
        return []
    return [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []


def clean_str(value: Any) -> Optional[str]:
    '''Los strings que empiezan con `$` son referencias internas de RSC.'''
    if not isinstance(value, str) or value.startswith('$'):
        return None
    return value.strip() or None


def parse_iso_date(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value[:4].isdigit():
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def _decode_chunks(raw: str) -> Iterator[str]:
    for match in _RSC_CHUNK.finditer(raw):
        try:
            yield json.loads(match.group(1))
        except ValueError:
            continue
