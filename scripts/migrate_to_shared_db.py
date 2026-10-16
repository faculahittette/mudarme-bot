"""Copia las publicaciones de la base SQLite local a la base compartida.

Uso (desde la carpeta del repo, con `database_url` ya cargado en config.yaml):
    venv\\Scripts\\python.exe scripts\\migrate_to_shared_db.py
    venv\\Scripts\\python.exe scripts\\migrate_to_shared_db.py --sqlite otra.db

Es idempotente: lo que ya existe en destino (mismo sha o url) se saltea, y se
conserva el flag `sent` para no reenviar lo que ya llego al grupo.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from posting_app.database import (  # noqa: E402
    Posting,
    PostingRepository,
    configure_database,
    create_db_and_tables,
    database_label,
)

COLUMNS = ('sha', 'url', 'title', 'price', 'location', 'description', 'sent')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--sqlite', default=str(ROOT / 'scrapdep.db'))
    parser.add_argument('--config', default=str(ROOT / 'config.yaml'))
    args = parser.parse_args()

    with open(args.config, encoding='utf-8') as fh:
        url = (yaml.safe_load(fh) or {}).get('database_url')
    configure_database(url)
    if database_label().startswith('sqlite'):
        sys.exit('No hay base compartida configurada: completa `database_url` en config.yaml.')

    create_db_and_tables()
    with sqlite3.connect(args.sqlite) as src:
        rows = src.execute(f"SELECT {', '.join(COLUMNS)} FROM posting ORDER BY id").fetchall()

    repo = PostingRepository()
    copied = sum(
        repo.create_posting(Posting(**dict(zip(COLUMNS, row))))
        for row in rows
    )
    print(f'Destino: {database_label()}')
    print(f'{len(rows)} publicaciones leidas, {copied} copiadas, {len(rows) - copied} ya estaban.')


if __name__ == '__main__':
    main()
