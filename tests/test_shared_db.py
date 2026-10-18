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
