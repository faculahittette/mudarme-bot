import pytest

from posting_app.database import Posting
from posting_app.prices import Price, parse_price, price_drop
from posting_app.services import PostingService
from telegram_app.services import TelegramService


# ---------------------------------------------------------------- Precios

@pytest.mark.parametrize('text, expected', [
    ('USD 229,000', Price('USD', 229000)),          # BNA / RE/MAX
    ('US$ 185.000', Price('USD', 185000)),          # Mercado Libre
    ('USD 180.000 + $ 90.000 expensas', Price('USD', 180000)),
    ('U$S 210.000,00', Price('USD', 210000)),
    ('$ 95.000.000', Price('ARS', 95000000)),
    ('Consultar precio', None),
    ('', None),
    (None, None),
])
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_price_drop_only_when_cheaper_in_same_currency():
    assert price_drop('USD 229,000', 'USD 215,000') == 6.1
    assert price_drop('USD 229.000', 'USD 229,000') is None   # mismo monto, otro formato
    assert price_drop('USD 200.000', 'USD 210.000') is None   # subio
    assert price_drop('USD 200.000', '$ 150.000.000') is None  # cambio de moneda
    assert price_drop('Consultar precio', 'USD 200.000') is None


# ---------------------------------------------------------------- Servicio

class _Scraper:
    def __init__(self, postings):
        self._postings = set(postings)
        self.dated = []

    def get_postings_from_scraper(self):
        return self._postings

    def add_publication_dates(self, postings):
        self.dated.extend(p.sha for p in postings)


class _Repo:
    def __init__(self, stored):
        self.stored = {p.sha: p for p in stored}
        self.created = []
        self.price_updates = []

    def get_postings_by_sha(self, shas):
        return {s: self.stored[s] for s in shas if s in self.stored}

    def create_posting(self, posting):
        self.created.append(posting.sha)
        return True

    def update_price(self, sha, old_price, new_price, notify_drop):
        self.price_updates.append((sha, old_price, new_price, notify_drop))
        return True


def _p(sha, price):
    return Posting(sha=sha, url=f'https://x/{sha}', price=price)


def _run(stored, scraped):
    scraper, repo = _Scraper(scraped), _Repo(stored)
    PostingService(scraper_service=scraper, repository=repo).scrap_and_create_postings()
    return scraper, repo


def test_new_postings_are_saved_and_only_they_get_publication_date():
    scraper, repo = _run(stored=[_p('viejo', 'USD 200.000')],
                         scraped=[_p('viejo', 'USD 200.000'), _p('nuevo', 'USD 150.000')])
    assert repo.created == ['nuevo']
    assert scraper.dated == ['nuevo']
    assert repo.price_updates == []


def test_price_drop_is_registered_for_notification():
    _, repo = _run(stored=[_p('a', 'USD 229.000')], scraped=[_p('a', 'USD 215.000')])
    assert repo.price_updates == [('a', 'USD 229.000', 'USD 215.000', True)]


def test_price_rise_updates_silently():
    _, repo = _run(stored=[_p('a', 'USD 200.000')], scraped=[_p('a', 'USD 210.000')])
    assert repo.price_updates == [('a', 'USD 200.000', 'USD 210.000', False)]


def test_missing_price_does_not_overwrite_stored_one():
    _, repo = _run(stored=[_p('a', 'USD 200.000')], scraped=[_p('a', 'Consultar precio')])
    assert repo.price_updates == []


# ---------------------------------------------------------------- Mensaje

def test_drop_message_shows_old_and_new_price():
    posting = Posting(sha='a', url='https://x/a', title='PH tríplex', location='Caballito',
                      price='USD 215,000', previous_price='USD 229,000', published='hace 8 días')
    svc = TelegramService(bot_token='t', chat_room='c')
    for msg in (svc.format_posting_to_message(posting), svc.format_minimal_message(posting)):
        assert msg.startswith('📉<b>Bajó de precio (-6.1%)</b>')
        assert '<s>USD 229,000</s> → <b>USD 215,000</b>' in msg
    assert 'Publicado' not in svc.format_posting_to_message(posting)
