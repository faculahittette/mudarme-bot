#!/usr/bin/env python3
"""Generate and send a short daily summary to the configured Telegram chat.
Usage: ./venv/bin/python scripts/daily_report.py
(Prefer to schedule via cron at desired hour.)
"""
import yaml
from posting_app.database import PostingRepository
from telegram_app.services import TelegramService
from collections import Counter

cfg = yaml.safe_load(open('config.yaml'))
repo = PostingRepository()

postings = repo.get_unsent_postings()  # unsent
# compute totals
all_count = len(postings)
# group by source inferred from url
sources = Counter()
for p in postings:
    if 'mercadolibre' in p.url:
        sources['mercadolibre'] += 1
    elif 'zonaprop' in p.url:
        sources['zonaprop'] += 1
    elif 'argenprop' in p.url:
        sources['argenprop'] += 1
    else:
        sources['other'] += 1

msg_lines = [
    f"Daily summary:\nUnsents total: {all_count}",
    f"MercadoLibre: {sources.get('mercadolibre',0)}",
    f"ZonaProp: {sources.get('zonaprop',0)}",
    f"Argenprop: {sources.get('argenprop',0)}",
]

# attach recent failures
try:
    with open('send_failures.log','r',encoding='utf-8') as fh:
        last = list(fh)[-5:]
    if last:
        msg_lines.append('\nLast failures:')
        for l in last:
            msg_lines.append(l[:300])
except FileNotFoundError:
    pass

msg = '\n'.join(msg_lines)
tele = TelegramService(bot_token=cfg['bot_token'], chat_room=cfg['chat_room'])
# send as a single message
ok = tele.send_telegram_message(msg)
print('Report sent:', ok)
