import pytest

from scraper_app.gateways import ArgenpropGateway, BnaGateway
from scraper_app.gateways.base import BaseGateway, SourceUnavailable


class _Flaky(BaseGateway):
    _name = 'Flaky'
    retry_wait_seconds = 0

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def _request_once(self, url, quiet):
        self.calls += 1
        return self._responses.pop(0)


def test_retries_a_failed_request_once():
    gw = _Flaky(['', '<html>ok</html>'])
    assert gw.make_request('u') == '<html>ok</html>'
    assert gw.calls == 2


def test_raises_after_all_attempts():
    gw = _Flaky(['', '', 'nunca'])
    with pytest.raises(SourceUnavailable):
        gw.make_request('u')
    assert gw.calls == 2


def test_backoff_doubles_the_wait(monkeypatch):
    waits = []
    monkeypatch.setattr('scraper_app.gateways.base.time.sleep', waits.append)
    gw = _Flaky(['', '', '', 'ok'])
    gw.attempts, gw.retry_wait_seconds = 4, 5
    assert gw.make_request('u') == 'ok'
    assert waits == [5, 10, 20]


class _Response:
    def __init__(self, status_code, text):
        self.status_code, self.text = status_code, text


def test_anti_bot_202_counts_as_failure():
    class _Gw(BaseGateway):
        _name = 'Gw'
        retry_wait_seconds = 0
        clients = [('fake', lambda: type('S', (), {'get': lambda self, url, timeout: _Response(202, 'JavaScript is disabled')})())]
    with pytest.raises(SourceUnavailable):
        _Gw().make_request('u')


def test_slow_or_blocking_sites_get_more_patience():
    assert ArgenpropGateway.attempts == 3 and ArgenpropGateway.retry_wait_seconds == 10
    assert BnaGateway.timeout_seconds == 60


# ------------------------------------------- Ritmo y sesion (anti-robots)

def test_argenprop_pages_use_canonical_suffix():
    gw = ArgenpropGateway()
    url = 'https://www.argenprop.com/ph/venta/x/apto-credito?desde-65-m2-cubiertos{}'
    assert [url.format(gw.page_param(p)) for p in (1, 2)] == [
        'https://www.argenprop.com/ph/venta/x/apto-credito?desde-65-m2-cubiertos',
        'https://www.argenprop.com/ph/venta/x/apto-credito?desde-65-m2-cubiertos&pagina-2',
    ]


def test_min_interval_is_shared_between_searches_of_the_same_site(monkeypatch):
    import scraper_app.gateways.base as base
    clock = iter([100.0, 101.0, 101.0])
    waits = []
    monkeypatch.setattr(base.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(base.time, 'sleep', waits.append)
    monkeypatch.setattr(base, '_last_request_at', {})

    class _Paced(_Flaky):
        min_interval_seconds = 4

    _Paced(['ok']).make_request('u1')   # primera: no espera
    _Paced(['ok']).make_request('u2')   # otra busqueda, mismo sitio, 1s despues
    assert waits == [3.0]


def test_reuse_session_keeps_one_session_per_site(monkeypatch):
    import scraper_app.gateways.base as base
    monkeypatch.setattr(base, '_sessions', {})
    created = []

    def factory():
        created.append(1)
        return type('S', (), {'get': lambda self, url, timeout: _Response(200, 'ok')})()

    class _Reuse(BaseGateway):
        _name = 'Reuse'
        reuse_session = True
        clients = [('fake', factory)]

    _Reuse().make_request('a')
    _Reuse().make_request('b')
    assert len(created) == 1
