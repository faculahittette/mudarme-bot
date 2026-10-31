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
