from scraper_app.gateways.base import BaseGateway


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


def test_gives_up_after_all_attempts():
    gw = _Flaky(['', '', 'nunca'])
    assert gw.make_request('u') == ''
    assert gw.calls == 2
