'''Simulacro de "apto credito por descripcion": corre esas busquedas, entra a
cada aviso sin la marca y muestra que mandaria a Telegram, SIN guardar nada en
la base ni mandar mensajes. Sirve para revisar falsos positivos antes de
activarlo o despues de tocar las reglas de scraper_app/apto_credito.py.

Solo LEE la base (para saltear los avisos que ya se mandaron) y no crea
tablas ni columnas. Deja el detalle tambien en apto_simulacro.log.

Uso (desde la carpeta del repo):
    venv\\Scripts\\python scripts\\apto_credito_simulacro.py
    venv\\Scripts\\python scripts\\apto_credito_simulacro.py --sitio zonaprop
'''
import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import bindparam, text  # noqa: E402

import posting_app.database as db  # noqa: E402
from main import APTO_POR_DESCRIPCION, Config, build_searches, load_config_dict  # noqa: E402
from posting_app.apto_credito_service import AptoCreditoPorDescripcionService  # noqa: E402
from run_log import tee_output_to  # noqa: E402
from scraper_app.apto_credito import texto_del_aviso  # noqa: E402
from scraper_app.services import ScraperServiceFactory  # noqa: E402

_FRASE = re.compile(r'.{0,60}apto\s*(?:a\s+|para\s+)?cr[eé]d.{0,40}', re.IGNORECASE)


class _ReadOnlyPostings:
    '''Lee que avisos ya existen (solo la columna sha, asi funciona aunque la
    base todavia no tenga las columnas nuevas) y anota en vez de guardar.'''

    def __init__(self):
        self.would_send = []

    def get_postings_by_sha(self, shas: Iterable[str]) -> Dict[str, bool]:
        shas = list(set(shas))
        if not shas:
            return {}
        query = text('SELECT sha FROM posting WHERE sha IN :shas').bindparams(
            bindparam('shas', expanding=True))
        with db.engine.connect() as conn:
            return {row[0]: True for row in conn.execute(query, {'shas': shas})}

    def create_posting(self, posting) -> bool:
        self.would_send.append(posting)
        return True


class _NoChecks:
    '''Como si nada se hubiera revisado nunca; anota los veredictos.'''

    def __init__(self):
        self.veredictos: Dict[str, str] = {}

    def checked_shas(self, shas: Iterable[str]) -> Set[str]:
        return set()

    def save(self, sha: str, url: str, veredicto: str) -> None:
        self.veredictos[sha] = veredicto


class _RememberingScraper:
    '''Envuelve el scraper real para guardar el HTML y poder mostrar la frase.'''

    def __init__(self, scraper):
        self._scraper = scraper
        self.pages: Dict[str, str] = {}

    def __getattr__(self, name):
        return getattr(self._scraper, name)

    def fetch_detail(self, url):
        html = self._scraper.fetch_detail(url)
        if html is not None:
            self.pages[url] = html
        return html


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--sitio', help='solo este sitio (zonaprop, argenprop, mercadolibre)')
    args = parser.parse_args()

    tee_output_to(ROOT / 'apto_simulacro.log')
    config = Config(**load_config_dict(ROOT / 'config.yaml', ROOT / 'searches.yaml', os.environ))
    db.configure_database(config.database_url)
    searches = [s for s in build_searches(config)
                if s.kind == APTO_POR_DESCRIPCION and (not args.sitio or s.site == args.sitio)]

    total: List[str] = []
    for search in searches:
        print(f'\n=== {search.site}: {search.url[:110]}')
        scraper = _RememberingScraper(ScraperServiceFactory.build(
            site=search.site, pages=config.pages, full_url=search.url))
        postings, checks = _ReadOnlyPostings(), _NoChecks()
        AptoCreditoPorDescripcionService(search.site, scraper, postings, checks).scrap_and_create_postings()
        for posting in postings.would_send:
            frase = _FRASE.search(texto_del_aviso(search.site, scraper.pages[posting.url]))
            line = f'MANDARIA | {posting.title[:70]} | {posting.price}\n    "{frase.group(0) if frase else ""}"\n    {posting.url}'
            print(line)
            total.append(line)
        resumen = {v: list(checks.veredictos.values()).count(v) for v in set(checks.veredictos.values())}
        print(f'--- veredictos: {resumen}')

    print(f'\n===== TOTAL que mandaria: {len(total)} (no se guardo ni se mando nada) =====')


if __name__ == '__main__':
    main()
