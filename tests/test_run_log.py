import io

from run_log import _Tee


def test_tee_writes_to_both_and_strips_colors_from_file():
    console, log = io.StringIO(), io.StringIO()
    tee = _Tee(console, log)
    tee.write('\x1b[32mZonaprop responded OK!\x1b[0m\n')
    assert console.getvalue() == '\x1b[32mZonaprop responded OK!\x1b[0m\n'
    assert log.getvalue() == 'Zonaprop responded OK!\n'
    assert tee.isatty() == console.isatty()
