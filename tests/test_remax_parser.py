from pathlib import Path

from scraper_app.parsers.remax import RemaxParser

FIXTURE = Path(__file__).parent / 'fixtures' / 'remax_sample.json'


def test_remax_parser_extracts_postings():
    parser = RemaxParser()
    parser.get_soup_object(html=FIXTURE.read_text(encoding='utf-8'))
    postings = parser.extract_data()

    assert len(postings) == 2
    by_url = {p.url: p for p in postings}

    p = by_url['https://www.remax.com.ar/listings/venta-3-amb-a-estrenar-en-villa-luro-apto-credito']
    assert p.title == 'VENTA 3 AMB A ESTRENAR EN VILLA LURO APTO CREDITO'
    assert p.location == 'Villa Luro, Capital Federal'
    assert 'USD' in p.price
    assert '69.23 m' in p.description
    assert p.sha


def test_remax_parser_handles_bad_json():
    parser = RemaxParser()
    parser.get_soup_object(html='<html>403 Forbidden</html>')
    assert parser.extract_data() == set()
