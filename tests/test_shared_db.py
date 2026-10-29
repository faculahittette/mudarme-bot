'''Repositorio contra SQLite y, si TEST_DATABASE_URL apunta a Postgres, contra Postgres.'''
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlmodel import SQLModel

import posting_app.database as db
from posting_app.database import Posting, PostingRepository

URLS = ['sqlite:///{tmp}/test.db']
if os.environ.get('TEST_DATABASE_URL'):
    URLS.append(os.environ['TEST_DATABASE_URL'])


@pytest.fixture(params=URLS)
def repo(request, tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    db.configure_database(request.param.format(tmp=tmp_path))
    SQLModel.metadata.drop_all(db.engine)
    db.create_db_and_tables()
    yield PostingRepository()
    SQLModel.metadata.drop_all(db.engine)


def _posting(sha='a'):
    return Posting(sha=sha, url=f'https://x/{sha}', title='t')


def test_duplicate_insert_is_ignored(repo):
    assert repo.create_posting(_posting()) is True
    assert repo.create_posting(_posting()) is False  # ej: la guardo la otra compu


def test_only_one_claim_wins_even_concurrently(repo):
    repo.create_posting(_posting())
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: repo.claim_for_sending('a'), range(8)))
    assert results.count(True) == 1
    assert repo.get_unsent_postings() == []


def test_release_claim_makes_it_pending_again(repo):
    repo.create_posting(_posting())
    assert repo.claim_for_sending('a')
    repo.release_claim('a')
    assert [p.sha for p in repo.get_unsent_postings()] == ['a']


def test_env_var_wins_over_config(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path}/env.db')
    db.configure_database(f'sqlite:///{tmp_path}/config.db')
    assert db.database_label().endswith('env.db')


def test_adds_published_column_to_existing_table(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / 'vieja.db'
    with sqlite3.connect(path) as c:  # tabla como estaba antes de `published`
        c.execute('CREATE TABLE posting (id INTEGER PRIMARY KEY, sha VARCHAR UNIQUE, url VARCHAR UNIQUE, '
                  'title VARCHAR, price VARCHAR, location VARCHAR, description VARCHAR, sent BOOLEAN)')
        c.execute("INSERT INTO posting (sha, url, sent) VALUES ('a', 'https://x/a', 1)")
    monkeypatch.delenv('DATABASE_URL', raising=False)
    db.configure_database(f'sqlite:///{path}')
    db.create_db_and_tables()
    db.create_db_and_tables()  # idempotente
    assert PostingRepository().create_posting(Posting(sha='b', url='https://x/b', published='hoy'))


def test_price_drop_marks_pending_once(repo):
    repo.create_posting(Posting(sha='a', url='https://x/a', price='USD 229.000'))
    assert repo.claim_for_sending('a')  # ya se habia mandado
    # Dos compus detectan la misma baja: solo una la registra.
    assert repo.update_price('a', 'USD 229.000', 'USD 215.000', notify_drop=True) is True
    assert repo.update_price('a', 'USD 229.000', 'USD 215.000', notify_drop=True) is False
    [pending] = repo.get_unsent_postings()
    assert (pending.price, pending.previous_price) == ('USD 215.000', 'USD 229.000')


def test_price_rise_does_not_resend(repo):
    repo.create_posting(Posting(sha='a', url='https://x/a', price='USD 200.000'))
    assert repo.claim_for_sending('a')
    assert repo.update_price('a', 'USD 200.000', 'USD 210.000', notify_drop=False)
    assert repo.get_unsent_postings() == []
    assert repo.get_postings_by_sha(['a', 'zz'])['a'].price == 'USD 210.000'


class _Scraper:
    def __init__(self, postings):
        self._postings = set(postings)

    def get_postings_from_scraper(self):
        return self._postings

    def add_publication_dates(self, postings):
        pass


def test_service_with_new_and_known_postings_in_same_run(repo):
    '''Regresion: guardar un aviso nuevo "expiraba" el objeto y despues fallaba
    con DetachedInstanceError al revisar precios en la misma corrida.'''
    from posting_app.services import PostingService
    repo.create_posting(Posting(sha='viejo', url='https://x/viejo', price='USD 200.000'))
    scraped = [
        Posting(sha='nuevo', url='https://x/nuevo', price='USD 150.000'),
        Posting(sha='viejo', url='https://x/viejo', price='USD 190.000'),
    ]
    PostingService(scraper_service=_Scraper(scraped), repository=repo).scrap_and_create_postings()
    stored = repo.get_postings_by_sha(['nuevo', 'viejo'])
    assert set(stored) == {'nuevo', 'viejo'}
    assert stored['viejo'].previous_price == 'USD 200.000'
