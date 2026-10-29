'''Reenvia a Telegram los avisos que HOY siguen publicados, cumplen todas las
busquedas/filtros configurados y tienen precio en dolares dentro de un rango.

Vuelve a scrapear todos los sitios (asi solo salen avisos vigentes) y no
modifica la base: solo la lee para completar "Publicado hace X".

Uso (desde la carpeta del repo):
    venv\\Scripts\\python scripts\\reenviar_disponibles.py 175000 210000 --dry-run
    venv\\Scripts\\python scripts\\reenviar_disponibles.py 175000 210000
'''
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import posting_app.database as db  # noqa: E402
from main import _SITE_KEYS, Config, as_url_list, load_config_dict  # noqa: E402
from posting_app.prices import parse_price  # noqa: E402
from scraper_app.parsers import BaseParser, BnaParser  # noqa: E402
from scraper_app.services import ScraperServiceFactory  # noqa: E402
from telegram_app.services import TelegramService  # noqa: E402


def _searches(config: Config) -> Iterator[Tuple[str, str, Optional[BaseParser]]]:
    '''(sitio, url, parser) de cada busqueda configurada.'''
    for site, key in _SITE_KEYS.items():
        if site == 'bna':
            if config.bna:
                parser = BnaParser(config.bna.build_filter())
                for url in as_url_list(config.bna.url):
                    yield site, url, parser
            continue
        for url in as_url_list(getattr(config, key)):
            yield site, url, None


def _usd(posting: db.Posting) -> Optional[int]:
    price = parse_price(posting.price)
    return price.amount if price and price.currency == 'USD' else None


def scrape_available(config: Config) -> Dict[str, db.Posting]:
    found: Dict[str, db.Posting] = {}
    for site, url, parser in _searches(config):
        try:
            scraper = ScraperServiceFactory.build(site, config.pages, url, parser)
            postings = scraper.get_postings_from_scraper()
        except Exception as ex:  # noqa: BLE001
            print(f'ERROR {site}: {ex!r}')
            continue
        print(f'{site}: {len(postings)} avisos vigentes')
        for p in postings:
            found.setdefault(p.sha, p)
    return found


def main(min_usd: int, max_usd: int, dry_run: bool) -> None:
    config = Config(**load_config_dict(ROOT / 'config.yaml', ROOT / 'searches.yaml', os.environ))
    db.configure_database(config.database_url)

    found = scrape_available(config)
    in_range = sorted(
        (p for p in found.values() if _usd(p) and min_usd <= _usd(p) <= max_usd),
        key=_usd,
    )
    known = db.PostingRepository().get_postings_by_sha(p.sha for p in in_range)
    for p in in_range:
        p.published = p.published or getattr(known.get(p.sha), 'published', None)

    print(f'\n{len(in_range)} avisos vigentes entre USD {min_usd} y USD {max_usd}:')
    for p in in_range:
        print(f'  {p.price:>14}  {(p.title or "")[:55]}  {p.url}')
    if dry_run or not in_range:
        return

    telegram = TelegramService(bot_token=config.bot_token, chat_room=config.chat_room)
    header = f'\U0001F501 <b>Disponibles hoy: {len(in_range)} avisos entre USD {min_usd:,} y USD {max_usd:,}</b>'
    telegram.send_telegram_message(header.replace(',', '.'))
    sent = sum(telegram.send_with_retries(p, max_retries=3, backoff_base=2) for p in in_range)
    print(f'Enviados: {sent}/{len(in_range)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('min_usd', type=int)
    parser.add_argument('max_usd', type=int)
    parser.add_argument('--dry-run', action='store_true', help='Solo listar, no mandar.')
    args = parser.parse_args()
    main(args.min_usd, args.max_usd, args.dry_run)
