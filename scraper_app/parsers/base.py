from abc import ABC
from hashlib import sha1
from typing import Optional, Set

from bs4 import BeautifulSoup

from posting_app.database import Posting


class BaseParser(ABC):
    #: URLs de TODOS los avisos de la ultima pagina parseada, antes de filtrar
    #: o deduplicar contra la base. Lo usa ScraperService para cortar la
    #: paginacion cuando una pagina no trae nada nuevo. `None` = el parser no
    #: lo informa y se recorren siempre las `pages` configuradas.
    page_keys: Optional[Set[str]] = None

    def get_soup_object(self, html: str):
        '''
        Taking HTML code as an entry, returns
        a BeautifulSoup object of the HTML code
        '''
        self.soup = BeautifulSoup(html, 'html.parser')
    
    def get_id(self, text: str) -> str:
        '''Get a SHA1 hash to identify each object.

        If `text` looks like a URL, normalize it by removing query
        parameters and fragments so the same resource with different
        query strings yields the same id (avoids duplicates).
        '''
        try:
            from urllib.parse import urlparse, urlunparse

            p = urlparse(text)
            if p.scheme and p.netloc:
                # Normalize path (remove trailing slash), drop query and fragment
                normalized = urlunparse((p.scheme, p.netloc, p.path.rstrip('/'), '', '', ''))
                _id = sha1(normalized.lower().encode('utf-8')).hexdigest()
                return _id
        except Exception:
            # If parsing fails, fall back to raw text
            pass

        _id = sha1(text.lower().encode('utf-8')).hexdigest()
        return _id
    
    def sanitize_text(self, text):
        '''
        Sometimes the message comes out weirdly from the html
        this fixes it for you.
        '''
        return ' '.join(text.split())

    def extract_data(self) -> Set[Posting]:
        pass