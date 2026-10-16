'''Duplica la salida de consola a un archivo de log (como `tee`).

Asi la ventana sigue mostrando lo que hace el bot en vivo (con colores) y,
ademas, queda `last_run.log` para revisar despues una corrida que se ejecuto
sola desde el Programador de tareas.
'''

import re
import sys
from pathlib import Path
from typing import TextIO

_ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')


class _Tee:
    '''Escribe en la consola original y, sin codigos de color, en el archivo.'''

    def __init__(self, console: TextIO, log_file: TextIO):
        self._console = console
        self._log = log_file

    def write(self, text: str) -> int:
        self._console.write(text)
        self._log.write(_ANSI.sub('', text))
        return len(text)

    def flush(self) -> None:
        self._console.flush()
        self._log.flush()

    def __getattr__(self, name):
        # isatty, encoding, fileno...: que rich vea la consola real.
        return getattr(self._console, name)


def tee_output_to(log_path: Path) -> None:
    '''Redirige stdout/stderr para que tambien se graben en `log_path`.'''
    log_file = open(log_path, 'w', encoding='utf-8')
    sys.stdout = _Tee(sys.stdout, log_file)
    sys.stderr = _Tee(sys.stderr, log_file)
