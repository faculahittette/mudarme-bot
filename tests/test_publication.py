from datetime import date, datetime, timezone

from posting_app.database import Posting
from scraper_app.publication import label_from_html, relative_label
from scraper_app.services import ScraperService
from telegram_app.services import TelegramService


def test_label_from_zonaprop_and_mercadolibre_html():
    assert label_from_html("... 'Publicado hace 13 días' \\n const x") == 'hace 13 días'
    assert label_from_html('<span>Departamento en Venta  |  Publicado hace 6 meses</span>') == 'hace 6 meses'
    assert label_from_html('Publicado hoy') == 'hoy'
    assert label_from_html('Publicado por múltiples inmobiliarias') is None
    assert label_from_html('') is None


def test_relative_label():
    today = date(2026, 10, 17)
    assert relative_label(datetime(2026, 7, 1, 13, 35, tzinfo=timezone.utc), today) == 'hace 3 meses'
    assert relative_label(date(2026, 10, 4), today) == 'hace 13 días'
    assert relative_label(date(2026, 10, 16), today) == 'ayer'
    assert relative_label(None, today) is None


class _DetailGateway:
    paginated = False
    publication_in_detail_page = True

    def __init__(self):
        self.detail_calls = []

    def make_request(self, url, quiet=False):
        if quiet:
            self.detail_calls.append(url)
            return 'Publicado hace 5 días'
        return 'listado'


class _Parser:
    def get_soup_object(self, html):
        pass

    def extract_data(self):
        return {Posting(sha='a', url='https://x/a', title='t')}


def test_scraper_fetches_publication_on_demand():
    gw = _DetailGateway()
    svc = ScraperService(pages=1, url='u{}', gateway=gw, parser=_Parser())
    postings = svc.get_postings_from_scraper()
    assert gw.detail_calls == []  # el listado solo, sin visitar cada aviso
    svc.add_publication_dates(postings)
    assert [p.published for p in postings] == ['hace 5 días']
    assert gw.detail_calls == ['https://x/a']


def test_message_shows_publication_when_known():
    svc = TelegramService(bot_token='t', chat_room='c')
    with_date = Posting(sha='a', url='https://x', title='T', price='USD 1', location='L', published='hace 13 días')
    assert '📅<i>Publicado hace 13 días</i>' in svc.format_posting_to_message(with_date)
    without = Posting(sha='b', url='https://y', title='T', price='USD 1', location='L')
    assert 'Publicado' not in svc.format_posting_to_message(without)
