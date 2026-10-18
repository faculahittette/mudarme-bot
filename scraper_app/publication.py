'''Antiguedad de la publicacion ("hace 13 dias") para mostrar en Telegram.

Cada sitio la expone distinto:
  - BNA / Roomix: fecha exacta en sus datos  -> relative_label(fecha)
  - Zonaprop / Mercado Libre: solo en la pagina del aviso, como texto
    "Publicado hace 13 dias"                 -> label_from_html(html)
  - Argenprop / RE/MAX: no la exponen.
'''

import re
from datetime import date, datetime, timezone
from typing import Optional, Union

_PUBLISHED = re.compile(
    r'Publicado\s+(hace\s+(?:m[aá]s\s+de\s+)?\d+\s+(?:d[ií]as?|semanas?|mes(?:es)?|a[nñ]os?)|hoy|ayer)',
    re.IGNORECASE,
)


def label_from_html(html: str) -> Optional[str]:
    '''Extrae "hace 13 dias" / "hoy" / "ayer" del HTML de un aviso.'''
    match = _PUBLISHED.search(html or '')
    return ' '.join(match.group(1).split()).lower() if match else None


def relative_label(when: Union[date, datetime, None], today: Optional[date] = None) -> Optional[str]:
    '''Convierte una fecha en "hoy", "ayer", "hace N dias/meses".'''
    if when is None:
        return None
    if isinstance(when, datetime):
        when = when.astimezone(timezone.utc).date() if when.tzinfo else when.date()
    days = ((today or date.today()) - when).days
    if days <= 0:
        return 'hoy'
    if days == 1:
        return 'ayer'
    if days < 60:
        return f'hace {days} días'
    months = days // 30
    return f'hace {months} meses' if months < 24 else f'hace {days // 365} años'
