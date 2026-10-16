from pathlib import Path

import pytest

from main import BnaConfig
from scraper_app.parsers.bna import BnaParser
from scraper_app.parsers.roomix import RoomixParser
from scraper_app.services import ScraperService

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def empty_repo(monkeypatch):
    '''Aisla de la base real: ningun sha existe todavia.'''
    for module in ('bna', 'roomix'):
        monkeypatch.setattr(
            f'scraper_app.parsers.{module}.PostingRepository.get_posting_by_sha',
            lambda self, sha: None,
        )


# ---------------------------------------------------------------- Roomix

def test_roomix_parses_initial_results_split_across_chunks(empty_repo):
    parser = RoomixParser()
    parser.get_soup_object(html=(FIXTURES / 'roomix_sample.html').read_text(encoding='utf-8'))
    postings = {p.url: p for p in parser.extract_data()}

    assert len(postings) == 3
    p = postings['https://roomix.ai/propiedad/departamento-3-ambientes-caballito-norte-05ae4a1b']
    assert p.price == 'USD 119,500'
    assert p.location == 'Av Juan B Justo 4000, Caballito Norte, Caballito'
    assert '73 m2 cub' in p.description and '3 amb' in p.description
    assert parser.page_keys == set(postings)


def test_roomix_ignores_rsc_references_and_missing_price(empty_repo):
    parser = RoomixParser()
    parser.get_soup_object(html=(FIXTURES / 'roomix_sample.html').read_text(encoding='utf-8'))
    postings = {p.url.rsplit('-', 1)[-1]: p for p in parser.extract_data()}

    # location_address "$9:..." es una referencia RSC: cae a location_city
    assert postings['19cbb3fa'].location == 'Caballito'
    assert postings['2ec4dc71'].price == 'Consultar precio'


def test_roomix_without_results_returns_empty_page(empty_repo):
    parser = RoomixParser()
    parser.get_soup_object(html='<html>sin payload</html>')
    assert parser.extract_data() == set()
    assert parser.page_keys == set()


# ---------------------------------------------------------------- BNA

def _bna_parser(**overrides) -> BnaParser:
    cfg = BnaConfig(**{
        'tipos': ['Departamento', 'PH'],
        'antiguedad_max_anos': 15,
        'antiguedad_max_anos_por_tipo': {'PH': 20},
        'ambientes_min': 3,
        'superficie_cubierta_min_m2': 62,
        **overrides,
    })
    return BnaParser(cfg.build_filter())


def _parse(parser: BnaParser, payload: str):
    parser.get_soup_object(html=payload)
    return {p.url.rsplit('/', 1)[-1]: p for p in parser.extract_data()}


def test_bna_applies_local_filters(empty_repo):
    postings = _parse(_bna_parser(), (FIXTURES / 'bna_sample.json').read_text(encoding='utf-8'))

    # 3537: pasa (ambientes null no bloquea). 3539: PH de 18 anos pasa por override.
    # 3538 viejo, 3540 reservado, 3541 chico, 3542 tipo Local: afuera.
    assert set(postings) == {'3537', '3539'}
    p = postings['3537']
    assert p.url == 'https://mashogaresconbna.com.ar/propiedad/3537'
    assert p.price == 'USD 169,000'
    assert p.location.startswith('Caballito')
    assert 'Apto crédito BNA' in p.description


def test_bna_page_keys_include_filtered_items(empty_repo):
    parser = _bna_parser()
    _parse(parser, (FIXTURES / 'bna_sample.json').read_text(encoding='utf-8'))
    # Las claves cuentan TODO lo que vino en la pagina (no solo lo que pasa
    # filtros): si no, una pagina sin matches cortaria la paginacion antes de tiempo.
    assert len(parser.page_keys) == 6


@pytest.mark.parametrize('payload', [
    '{"internalStatus":"NO_CONTENT","message":"No se encontraron resultados"}',
    '<html>502</html>',
    '',
])
def test_bna_handles_empty_or_broken_responses(empty_repo, payload):
    parser = _bna_parser()
    assert _parse(parser, payload) == {}
    assert parser.page_keys == set()


# ---------------------------------------------------------------- Paginacion

class _Gateway:
    paginated = True
    first_page = 1

    def __init__(self, pages):
        self._pages = pages
        self.requested = []

    def make_request(self, url):
        self.requested.append(url)
        return self._pages.get(url, '')


class _KeysParser:
    '''Devuelve como page_keys lo que venga en el "html" (claves separadas por coma).'''

    def get_soup_object(self, html):
        self._html = html

    def extract_data(self):
        self.page_keys = {k for k in self._html.split(',') if k}
        return set()


def test_stops_when_page_is_empty():
    gw = _Gateway({'u1': 'a,b', 'u2': 'c'})
    ScraperService(pages=10, url='u{}', gateway=gw, parser=_KeysParser()).get_postings_from_scraper()
    assert gw.requested == ['u1', 'u2', 'u3']


def test_stops_when_site_repeats_a_page():
    # Zonaprop devuelve la pagina 1 si pedis una fuera de rango.
    gw = _Gateway({'u1': 'a,b', 'u2': 'a,b'})
    ScraperService(pages=10, url='u{}', gateway=gw, parser=_KeysParser()).get_postings_from_scraper()
    assert gw.requested == ['u1', 'u2']
