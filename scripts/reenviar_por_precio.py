'''Reenvia a Telegram los avisos guardados con precio en dolares dentro de un rango.

No modifica la base: solo vuelve a mandar los mensajes.

Uso (desde la carpeta del repo):
    venv\\Scripts\\python scripts\\reenviar_por_precio.py 180000 215000 --dry-run
    venv\\Scripts\\python scripts\\reenviar_por_precio.py 180000 215000
'''
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import argparse  # noqa: E402

from sqlmodel import Session, select  # noqa: E402

import posting_app.database as db  # noqa: E402
from main import Config, load_config_dict  # noqa: E402
from posting_app.prices import parse_price  # noqa: E402
from telegram_app.services import TelegramService  # noqa: E402


def main(min_usd: int, max_usd: int, dry_run: bool = False):
    config = Config(**load_config_dict(ROOT / 'config.yaml', ROOT / 'searches.yaml', os.environ))
    db.configure_database(config.database_url)
    print('Base:', db.database_label())

    with Session(db.engine) as session:
        postings = list(session.exec(select(db.Posting)))

    def usd(p):
        price = parse_price(p.price)
        return price.amount if price and price.currency == 'USD' else None

    in_range = sorted(
        (p for p in postings if usd(p) and min_usd <= usd(p) <= max_usd),
        key=usd,
    )
    print(f'{len(in_range)} avisos entre USD {min_usd} y USD {max_usd}')
    for p in in_range:
        print(f'  {p.price:>14}  {(p.title or "")[:60]}  {p.url}')
    if dry_run or not in_range:
        return

    telegram = TelegramService(bot_token=config.bot_token, chat_room=config.chat_room)
    telegram.send_telegram_message(
        f'\U0001F501 <b>Reenvío: {len(in_range)} avisos entre '
        f'USD {min_usd:,} y USD {max_usd:,}</b>'.replace(',', '.')
    )
    sent = sum(telegram.send_with_retries(p, max_retries=3, backoff_base=2) for p in in_range)
    print(f'Enviados: {sent}/{len(in_range)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('min_usd', type=int)
    parser.add_argument('max_usd', type=int)
    parser.add_argument('--dry-run', action='store_true', help='Solo listar, no mandar.')
    args = parser.parse_args()
    main(args.min_usd, args.max_usd, args.dry_run)
