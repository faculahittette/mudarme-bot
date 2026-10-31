'''Reintento de busquedas incompletas y alerta por Telegram (main.py).'''
import main
from main import Config, describe_search, failure_alert, scrape_send_and_report


class _FakeTelegram:
    def __init__(self, **_):
        self.alerts = []

    def send_telegram_message(self, msg):
        self.alerts.append(msg)
        return True


def _setup(monkeypatch, results_per_round, retry_after=300):
    '''`results_per_round`: por cada ronda, que busquedas fallan.'''
    rounds, sleeps = [], []
    telegram = _FakeTelegram()

    def fake_run(searches, pages, factories=None):
        rounds.append([s[0] for s in searches])
        failing = results_per_round[len(rounds) - 1]
        return [s for s in searches if s[0] in failing]

    monkeypatch.setattr(main, 'run_searches', fake_run)
    monkeypatch.setattr(main, 'send_unsent_postings', lambda tg: None)
    monkeypatch.setattr(main, 'sleep', sleeps.append)
    monkeypatch.setattr(main, 'TelegramService', lambda **kw: telegram)
    config = Config(bot_token='t', chat_room='c', retry_failed_after_seconds=retry_after)
    searches = [('zonaprop', 'https://z/a', None), ('argenprop', 'https://a/ph/venta', None)]
    scrape_send_and_report(config, searches)
    return rounds, sleeps, telegram.alerts


def test_all_ok_no_retry_no_alert(monkeypatch):
    rounds, sleeps, alerts = _setup(monkeypatch, [set()])
    assert rounds == [['zonaprop', 'argenprop']]
    assert sleeps == [] and alerts == []


def test_retries_only_failed_and_stays_quiet_if_it_recovers(monkeypatch):
    rounds, sleeps, alerts = _setup(monkeypatch, [{'argenprop'}, set()])
    assert rounds == [['zonaprop', 'argenprop'], ['argenprop']]
    assert sleeps == [300]
    assert alerts == []


def test_alerts_when_retry_also_fails(monkeypatch):
    rounds, sleeps, alerts = _setup(monkeypatch, [{'argenprop'}, {'argenprop'}])
    assert len(alerts) == 1
    assert 'argenprop · /ph/venta' in alerts[0]
    assert 'tambien en el reintento' in alerts[0]


def test_retry_disabled_alerts_right_away(monkeypatch):
    rounds, sleeps, alerts = _setup(monkeypatch, [{'argenprop'}], retry_after=0)
    assert rounds == [['zonaprop', 'argenprop']]
    assert sleeps == [] and len(alerts) == 1


def test_alert_escapes_html():
    msg = failure_alert([('x', 'https://h/<b>', None)], retried=True)
    assert '&lt;b&gt;' in msg


def test_describe_search_without_path():
    assert describe_search(('bna', 'https://h', None)) == 'bna'
