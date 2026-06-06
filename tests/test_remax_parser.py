from pathlib import Path

from scraper_app.parsers.remax import RemaxParser

FIXTURE = Path(__file__).parent / 'fixtures' / 'remax_sample.json'


def test_remax_parser_extracts_postings(monkeypatch):
    # Aislar del SQLite real: ningun sha existe todavia.
    monkeypatch.setattr(
        'scraper_app.parsers.remax.PostingRepository.get_posting_by_sha',
        lambda self, sha: None,
    )

    parser = RemaxParser()
    parser.get_soup_object(html=FIXTURE.read_text(encoding='utf-8'))
    postings = parser.extract_data()

    assert len(postings) == 2
    by_url = {p.url: p for p in postings}

    p = by_url['https://www.remax.com.ar/listings/depto-3-amb-caballito-apto-credito']
    assert p.title == 'Departamento 3 ambientes en Caballito'
    assert p.location == 'Caballito, Capital Federal'
    assert 'USD' in p.price
    assert '68 m' in p.description
    assert p.sha


def test_remax_parser_skips_seen(monkeypatch):
    # Si el repo dice que ya existe, no se incluye.
    monkeypatch.setattr(
        'scraper_app.parsers.remax.PostingRepository.get_posting_by_sha',
        lambda self, sha: object(),
    )
    parser = RemaxParser()
    parser.get_soup_object(html=FIXTURE.read_text(encoding='utf-8'))
    assert parser.extract_data() == set()


def test_remax_parser_handles_bad_json(monkeypatch):
    monkeypatch.setattr(
        'scraper_app.parsers.remax.PostingRepository.get_posting_by_sha',
        lambda self, sha: None,
    )
    parser = RemaxParser()
    parser.get_soup_object(html='<html>403 Forbidden</html>')
    assert parser.extract_data() == set()
