from pathlib import Path

from scraper_app.parsers.mercadolibre import MercadolibreParser

FIXTURE = Path(__file__).parent / 'fixtures' / 'mercadolibre_sample.html'


def _parse():
    parser = MercadolibreParser()
    parser.get_soup_object(html=FIXTURE.read_text(encoding='utf-8'))
    return parser, {p.url: p for p in parser.extract_data()}


def test_only_search_results_and_clean_urls():
    parser, postings = _parse()
    assert set(postings) == {
        'https://departamento.mercadolibre.com.ar/MLA-1739205676-neuquen-637-_JM',
        'https://departamento.mercadolibre.com.ar/MLA-1925002080-avenida-gaona-1248-_JM',
    }  # la publicidad fuera de la lista no entra
    assert parser.page_keys == set(postings)


def test_price_currency_and_attributes():
    _, postings = _parse()
    p = postings['https://departamento.mercadolibre.com.ar/MLA-1739205676-neuquen-637-_JM']
    assert p.price == 'US$ 185.000'
    assert p.description == '3 ambs. | 2 baños | 62 m² cubiertos'
    assert p.location == 'NEUQUEN 637, Caballito, Capital Federal'
    sin_precio = postings['https://departamento.mercadolibre.com.ar/MLA-1925002080-avenida-gaona-1248-_JM']
    assert sin_precio.price == 'Consultar precio'
