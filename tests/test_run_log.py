import io

from run_log import _Tee


def test_tee_writes_to_both_and_strips_colors_from_file():
    console, log = io.StringIO(), io.StringIO()
    tee = _Tee(console, log)
    tee.write('\x1b[32mZonaprop responded OK!\x1b[0m\n')
    assert console.getvalue() == '\x1b[32mZonaprop responded OK!\x1b[0m\n'
    assert log.getvalue() == 'Zonaprop responded OK!\n'
    assert tee.isatty() == console.isatty()


def test_tee_strips_terminal_hyperlinks():
    log = io.StringIO()
    _Tee(io.StringIO(), log).write('\x1b]8;id=1;file://C:/main.py\x1b\\main.py\x1b]8;;\x1b\\:110\n')
    assert log.getvalue() == 'main.py:110\n'
